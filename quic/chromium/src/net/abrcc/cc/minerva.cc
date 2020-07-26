#include "net/abrcc/cc/minerva.h"

#include <algorithm>
#include <cstdint>
#include <string>

#include "net/third_party/quiche/src/quic/core/congestion_control/prr_sender.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/rtt_stats.h"
#include "net/third_party/quiche/src/quic/core/crypto/crypto_protocol.h"
#include "net/third_party/quiche/src/quic/core/quic_constants.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_flags.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

#include "net/third_party/quiche/src/quic/platform/api/quic_mutex.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Waddress-of-packed-member"

namespace quic {

namespace {

/// ------------------------------------------------------------------
/// ------------------------ MinervaBytes ----------------------------
/// ------------------------------------------------------------------

// Constants based on TCP defaults.
// The following constants are in 2^10 fractions of a second instead of ms to
// allow a 10 shift right to divide.
const int kCubeScale = 40;  // 1024*1024^3 (first 1024 is from 0.100^3)
                            // where 0.100 is 100 ms which is the scaling
                            // round trip time.
const int kCubeCongestionWindowScale = 410;
// The cube factor for packets in bytes.
const uint64_t kCubeFactor =
    (UINT64_C(1) << kCubeScale) / kCubeCongestionWindowScale / kDefaultTCPMSS;

const float kDefaultCubicBackoffFactor = 0.7f;  // Default Cubic backoff factor.
// Additional backoff factor when loss occurs in the concave part of the Cubic
// curve. This additional backoff factor is expected to give up bandwidth to
// new concurrent flows and speed up convergence.
const float kBetaLastMax = 0.85f;

/// ------------------------------------------------------------------
/// ---------------------- TcpMinervaSenderBytes ---------------------
/// ------------------------------------------------------------------

// Constants based on TCP defaults.
const QuicByteCount kMaxBurstBytes = 3 * kDefaultTCPMSS;
// The minimum cwnd based on RFC 3782 (TCP NewReno) for cwnd reductions on a
// fast retransmission.
const QuicByteCount kDefaultMinimumCongestionWindow = 2 * kDefaultTCPMSS;

const QuicPacketCount kMaxResumptionCongestionWindow = 200;

}  // namespace


/// ------------------------------------------------------------------
/// ------------------------ MinervaBytes ----------------------------
/// ------------------------------------------------------------------

MinervaBytes::MinervaBytes() 
    : num_connections_(kDefaultNumConnections),
      epoch_(QuicTime::Zero()) {
 ResetCubicState();
}

void MinervaBytes::SetNumConnections(int num_connections) {
  num_connections_ = num_connections;
}

float MinervaBytes::Alpha() const {
  // TCPFriendly alpha is described in Section 3.3 of the CUBIC paper. Note that
  // beta here is a cwnd multiplier, and is equal to 1-beta from the paper.
  // We derive the equivalent alpha for an N-connection emulation as:
  const float beta = Beta();
  return 3 * num_connections_ * num_connections_ * (1 - beta) / (1 + beta);
}

float MinervaBytes::Beta() const {
  // kNConnectionBeta is the backoff factor after loss for our N-connection
  // emulation, which emulates the effective backoff of an ensemble of N
  // TCP-Reno connections on a single loss event. The effective multiplier is
  // computed as:
  return (num_connections_ - 1 + kDefaultCubicBackoffFactor) / num_connections_;
}

float MinervaBytes::BetaLastMax() const {
  // BetaLastMax is the additional backoff factor after loss for our
  // N-connection emulation, which emulates the additional backoff of
  // an ensemble of N TCP-Reno connections on a single loss event. The
  // effective multiplier is computed as:
  return (num_connections_ - 1 + kBetaLastMax) / num_connections_;
}

void MinervaBytes::ResetCubicState() {
  interface = MinervaInterface::GetInstance();
  epoch_ = QuicTime::Zero();             // Reset time.
  last_max_congestion_window_ = 0;
  acked_bytes_count_ = 0;
  estimated_tcp_congestion_window_ = 0;
  origin_point_congestion_window_ = 0;
  time_to_origin_point_ = 0;
  last_target_congestion_window_ = 0;
}

void MinervaBytes::OnApplicationLimited() {
  // When sender is not using the available congestion window, the window does
  // not grow. But to be RTT-independent, Cubic assumes that the sender has been
  // using the entire window during the time since the beginning of the current
  // "epoch" (the end of the last loss recovery period). Since
  // application-limited periods break this assumption, we reset the epoch when
  // in such a period. This reset effectively freezes congestion window growth
  // through application-limited periods and allows Cubic growth to continue
  // when the entire window is being used.
  epoch_ = QuicTime::Zero();
}

QuicByteCount MinervaBytes::CongestionWindowAfterPacketLoss(
    QuicByteCount current_congestion_window) {
  // Since bytes-mode Reno mode slightly under-estimates the cwnd, we
  // may never reach precisely the last cwnd over the course of an
  // RTT.  Do not interpret a slight under-estimation as competing traffic.
  if (current_congestion_window + kDefaultTCPMSS <
      last_max_congestion_window_) {
    // We never reached the old max, so assume we are competing with
    // another flow. Use our extra back off factor to allow the other
    // flow to go up.
    last_max_congestion_window_ =
        static_cast<int>(BetaLastMax() * current_congestion_window);
  } else {
    last_max_congestion_window_ = current_congestion_window;
  }
  epoch_ = QuicTime::Zero();  // Reset time.
  return static_cast<int>(current_congestion_window * Beta());
}

QuicByteCount MinervaBytes::CongestionWindowAfterAck(
    QuicByteCount acked_bytes,
    QuicByteCount current_congestion_window,
    QuicTime::Delta delay_min,
    QuicTime event_time) {
  acked_bytes_count_ += acked_bytes;

  if (!epoch_.IsInitialized()) {
    // First ACK after a loss event.
    QUIC_DVLOG(1) << "Start of epoch";
    epoch_ = event_time;               // Start of epoch.
    acked_bytes_count_ = acked_bytes;  // Reset count.
    // Reset estimated_tcp_congestion_window_ to be in sync with cubic.
    estimated_tcp_congestion_window_ = current_congestion_window;
    if (last_max_congestion_window_ <= current_congestion_window) {
      time_to_origin_point_ = 0;
      origin_point_congestion_window_ = current_congestion_window;
    } else {
      time_to_origin_point_ = static_cast<uint32_t>(
          cbrt(kCubeFactor *
               (last_max_congestion_window_ - current_congestion_window)));
      origin_point_congestion_window_ = last_max_congestion_window_;
    }
  }
  // Change the time unit from microseconds to 2^10 fractions per second. Take
  // the round trip time in account. This is done to allow us to use shift as a
  // divide operator.
  int64_t elapsed_time =
      ((event_time + delay_min - epoch_).ToMicroseconds() << 10) /
      kNumMicrosPerSecond;

  // Right-shifts of negative, signed numbers have implementation-dependent
  // behavior, so force the offset to be positive, as is done in the kernel.
  uint64_t offset = std::abs(time_to_origin_point_ - elapsed_time);

  QuicByteCount delta_congestion_window = (kCubeCongestionWindowScale * offset *
                                           offset * offset * kDefaultTCPMSS) >>
                                          kCubeScale;

  const bool add_delta = elapsed_time > time_to_origin_point_;
  DCHECK(add_delta ||
         (origin_point_congestion_window_ > delta_congestion_window));
  QuicByteCount target_congestion_window =
      add_delta ? origin_point_congestion_window_ + delta_congestion_window
                : origin_point_congestion_window_ - delta_congestion_window;
  // Limit the CWND increase to half the acked bytes.
  target_congestion_window =
      std::min(target_congestion_window,
               current_congestion_window + acked_bytes_count_ / 2);

  DCHECK_LT(0u, estimated_tcp_congestion_window_);
  // Increase the window by approximately Alpha * 1 MSS of bytes every
  // time we ack an estimated tcp window of bytes.  For small
  // congestion windows (less than 25), the formula below will
  // increase slightly slower than linearly per estimated tcp window
  // of bytes.
  estimated_tcp_congestion_window_ += acked_bytes_count_ *
                                      (Alpha() * kDefaultTCPMSS) /
                                      estimated_tcp_congestion_window_;
  acked_bytes_count_ = 0;

  // We have a new cubic congestion window.
  last_target_congestion_window_ = target_congestion_window;

  // Compute target congestion_window based on cubic target and estimated TCP
  // congestion_window, use highest (fastest).
  if (target_congestion_window < estimated_tcp_congestion_window_) {
    target_congestion_window = estimated_tcp_congestion_window_;
  }

  QUIC_DVLOG(1) << "Final target congestion_window: "
                << target_congestion_window;
  return target_congestion_window;
}

/// ------------------------------------------------------------------
/// ------------------------ MinervaInterface ------------------------
/// ------------------------------------------------------------------

MinervaInterface *MinervaInterface::GetInstance() {
  return GET_SINGLETON(MinervaInterface);
}

MinervaInterface::MinervaInterface()
  : parent(nullptr) 
  , min_rtt_(base::nullopt)
  , acked_bytes_(0)
  , link_weight_(base::nullopt) {}
MinervaInterface::~MinervaInterface() {}

void MinervaInterface::updateMinRtt() {
  if (parent == nullptr) {
    return;
  }
  
  QuicWriterMutexLock lock(&min_rtt_mutex_);
  int min_rtt = parent->rtt_stats_->min_rtt().ToMilliseconds(); 
  if (min_rtt == 0) {
    return;
  }
  min_rtt_ = min_rtt;
}

base::Optional<int> MinervaInterface::minRtt() const {
  if (parent == nullptr) {
    return base::nullopt;
  }
  
  QuicReaderMutexLock lock(&min_rtt_mutex_);
  return min_rtt_;
}


int MinervaInterface::ackedBytes() const {
  QuicReaderMutexLock lock(&acked_bytes_mutex_);
  return acked_bytes_;
}

void MinervaInterface::addAckedBytes(const int bytes) {
  QuicWriterMutexLock lock(&acked_bytes_mutex_);
  acked_bytes_ += bytes;
}

void MinervaInterface::resetAckedBytes() {
  QuicWriterMutexLock lock(&acked_bytes_mutex_);
  acked_bytes_ = 0;
}

void MinervaInterface::setLinkWeight(const double weight) {
  QuicWriterMutexLock lock(&link_weight_mutex_);
  link_weight_ = weight;
}

base::Optional<double> MinervaInterface::getLinkWeight() const {
  QuicReaderMutexLock lock(&link_weight_mutex_);
  return link_weight_;
}

/// ------------------------------------------------------------------
/// ---------------------- TcpMinervaSenderBytes ---------------------
/// ------------------------------------------------------------------

TcpMinervaSenderBytes::TcpMinervaSenderBytes(
    const RttStats* rtt_stats,
    QuicPacketCount initial_tcp_congestion_window,
    QuicPacketCount max_congestion_window,
    QuicConnectionStats* stats)
    : rtt_stats_(rtt_stats),
      stats_(stats),
      num_connections_(kDefaultNumConnections),
      min4_mode_(false),
      last_cutback_exited_slowstart_(false),
      slow_start_large_reduction_(false),
      num_acked_packets_(0),
      congestion_window_(initial_tcp_congestion_window * kDefaultTCPMSS),
      min_congestion_window_(kDefaultMinimumCongestionWindow),
      max_congestion_window_(max_congestion_window * kDefaultTCPMSS),
      slowstart_threshold_(max_congestion_window * kDefaultTCPMSS),
      initial_tcp_congestion_window_(initial_tcp_congestion_window *
                                     kDefaultTCPMSS),
      initial_max_tcp_congestion_window_(max_congestion_window *
                                         kDefaultTCPMSS),
      min_slow_start_exit_window_(min_congestion_window_),
      interface(MinervaInterface::GetInstance()) {
  interface->parent = this;
}

TcpMinervaSenderBytes::~TcpMinervaSenderBytes() {}

void TcpMinervaSenderBytes::AdjustNetworkParameters(const NetworkParams& params) {
  if (params.bandwidth.IsZero() || params.rtt.IsZero()) {
    return;
  }
  SetCongestionWindowFromBandwidthAndRtt(params.bandwidth, params.rtt);
}

void TcpMinervaSenderBytes::OnCongestionEvent(
    bool rtt_updated,
    QuicByteCount prior_in_flight,
    QuicTime event_time,
    const AckedPacketVector& acked_packets,
    const LostPacketVector& lost_packets) {
  if (rtt_updated && InSlowStart() &&
      hybrid_slow_start_.ShouldExitSlowStart(
          rtt_stats_->latest_rtt(), rtt_stats_->min_rtt(),
          GetCongestionWindow() / kDefaultTCPMSS)) {
    ExitSlowstart();
  }
  for (const LostPacket& lost_packet : lost_packets) {
    OnPacketLost(lost_packet.packet_number, lost_packet.bytes_lost,
                 prior_in_flight);
  }
  for (const AckedPacket acked_packet : acked_packets) {
    OnPacketAcked(acked_packet.packet_number, acked_packet.bytes_acked,
                  prior_in_flight, event_time);
  }

  // call interface update methods
  interface->updateMinRtt();
}

void TcpMinervaSenderBytes::OnPacketAcked(QuicPacketNumber acked_packet_number,
                                        QuicByteCount acked_bytes,
                                        QuicByteCount prior_in_flight,
                                        QuicTime event_time) {
  // add acked bytes to measure the instant rate measurement
  interface->addAckedBytes(acked_bytes);
  
  largest_acked_packet_number_.UpdateMax(acked_packet_number);
  if (InRecovery()) {
    prr_.OnPacketAcked(acked_bytes);
    return;
  }
  MaybeIncreaseCwnd(acked_packet_number, acked_bytes, prior_in_flight,
                    event_time);
  if (InSlowStart()) {
    hybrid_slow_start_.OnPacketAcked(acked_packet_number);
  }
}

void TcpMinervaSenderBytes::OnPacketSent(
    QuicTime /*sent_time*/,
    QuicByteCount /*bytes_in_flight*/,
    QuicPacketNumber packet_number,
    QuicByteCount bytes,
    HasRetransmittableData is_retransmittable) {
  if (InSlowStart()) {
    ++(stats_->slowstart_packets_sent);
  }

  if (is_retransmittable != HAS_RETRANSMITTABLE_DATA) {
    return;
  }
  if (InRecovery()) {
    prr_.OnPacketSent(bytes);
  }
  DCHECK(!largest_sent_packet_number_.IsInitialized() ||
         largest_sent_packet_number_ < packet_number);
  largest_sent_packet_number_ = packet_number;
  hybrid_slow_start_.OnPacketSent(packet_number);

  // call interface update methods
  interface->updateMinRtt();
}

bool TcpMinervaSenderBytes::CanSend(QuicByteCount bytes_in_flight) {
  if (InRecovery()) {
    return prr_.CanSend(GetCongestionWindow(), bytes_in_flight,
                        GetSlowStartThreshold());
  }
  if (GetCongestionWindow() > bytes_in_flight) {
    return true;
  }
  if (min4_mode_ && bytes_in_flight < 4 * kDefaultTCPMSS) {
    return true;
  }
  return false;
}

QuicBandwidth TcpMinervaSenderBytes::PacingRate(
    QuicByteCount /* bytes_in_flight */) const {
  // We pace at twice the rate of the underlying sender's bandwidth estimate
  // during slow start and 1.25x during congestion avoidance to ensure pacing
  // doesn't prevent us from filling the window.
  QuicTime::Delta srtt = rtt_stats_->SmoothedOrInitialRtt();
  const QuicBandwidth bandwidth =
      QuicBandwidth::FromBytesAndTimeDelta(GetCongestionWindow(), srtt);
  return bandwidth * (InSlowStart() ? 2 : (InRecovery() ? 1 : 1.25));
}

QuicBandwidth TcpMinervaSenderBytes::BandwidthEstimate() const {
  QuicTime::Delta srtt = rtt_stats_->smoothed_rtt();
  if (srtt.IsZero()) {
    // If we haven't measured an rtt, the bandwidth estimate is unknown.
    return QuicBandwidth::Zero();
  }
  return QuicBandwidth::FromBytesAndTimeDelta(GetCongestionWindow(), srtt);
}

bool TcpMinervaSenderBytes::InSlowStart() const {
  return GetCongestionWindow() < GetSlowStartThreshold();
}

bool TcpMinervaSenderBytes::IsCwndLimited(QuicByteCount bytes_in_flight) const {
  const QuicByteCount congestion_window = GetCongestionWindow();
  if (bytes_in_flight >= congestion_window) {
    return true;
  }
  const QuicByteCount available_bytes = congestion_window - bytes_in_flight;
  const bool slow_start_limited =
      InSlowStart() && bytes_in_flight > congestion_window / 2;
  return slow_start_limited || available_bytes <= kMaxBurstBytes;
}

bool TcpMinervaSenderBytes::InRecovery() const {
  return largest_acked_packet_number_.IsInitialized() &&
         largest_sent_at_last_cutback_.IsInitialized() &&
         largest_acked_packet_number_ <= largest_sent_at_last_cutback_;
}

bool TcpMinervaSenderBytes::ShouldSendProbingPacket() const {
  return false;
}

void TcpMinervaSenderBytes::OnRetransmissionTimeout(bool packets_retransmitted) {
  largest_sent_at_last_cutback_.Clear();
  if (!packets_retransmitted) {
    return;
  }
  hybrid_slow_start_.Restart();
  HandleRetransmissionTimeout();
}

void TcpMinervaSenderBytes::SetCongestionWindowFromBandwidthAndRtt(
    QuicBandwidth bandwidth,
    QuicTime::Delta rtt) {
  QuicByteCount new_congestion_window = bandwidth.ToBytesPerPeriod(rtt);
  // Limit new CWND if needed.
  congestion_window_ =
      std::max(min_congestion_window_,
               std::min(new_congestion_window,
                        kMaxResumptionCongestionWindow * kDefaultTCPMSS));
}

void TcpMinervaSenderBytes::SetInitialCongestionWindowInPackets(
    QuicPacketCount congestion_window) {
  congestion_window_ = congestion_window * kDefaultTCPMSS;
}

void TcpMinervaSenderBytes::SetMinCongestionWindowInPackets(
    QuicPacketCount congestion_window) {
  min_congestion_window_ = congestion_window * kDefaultTCPMSS;
}

void TcpMinervaSenderBytes::SetNumEmulatedConnections(int num_connections) {
  num_connections_ = std::max(1, num_connections);
  cubic_.SetNumConnections(num_connections_);
}

void TcpMinervaSenderBytes::ExitSlowstart() {
  slowstart_threshold_ = congestion_window_;
}

void TcpMinervaSenderBytes::OnPacketLost(QuicPacketNumber packet_number,
                                       QuicByteCount lost_bytes,
                                       QuicByteCount prior_in_flight) {
  if (largest_sent_at_last_cutback_.IsInitialized() &&
      packet_number <= largest_sent_at_last_cutback_) {
    if (last_cutback_exited_slowstart_) {
      ++stats_->slowstart_packets_lost;
      stats_->slowstart_bytes_lost += lost_bytes;
      if (slow_start_large_reduction_) {
        // Reduce congestion window by lost_bytes for every loss.
        congestion_window_ = std::max(congestion_window_ - lost_bytes,
                                      min_slow_start_exit_window_);
        slowstart_threshold_ = congestion_window_;
      }
    }
    QUIC_DVLOG(1) << "Ignoring loss for largest_missing:" << packet_number
                  << " because it was sent prior to the last CWND cutback.";
    return;
  }
  ++stats_->tcp_loss_events;
  last_cutback_exited_slowstart_ = InSlowStart();
  if (InSlowStart()) {
    ++stats_->slowstart_packets_lost;
  }

  prr_.OnPacketLost(prior_in_flight);

  if (slow_start_large_reduction_ && InSlowStart()) {
    DCHECK_LT(kDefaultTCPMSS, congestion_window_);
    if (congestion_window_ >= 2 * initial_tcp_congestion_window_) {
      min_slow_start_exit_window_ = congestion_window_ / 2;
    }
    congestion_window_ = congestion_window_ - kDefaultTCPMSS;
  } else {
    congestion_window_ =
        cubic_.CongestionWindowAfterPacketLoss(congestion_window_);
  }
  if (congestion_window_ < min_congestion_window_) {
    congestion_window_ = min_congestion_window_;
  }
  slowstart_threshold_ = congestion_window_;
  largest_sent_at_last_cutback_ = largest_sent_packet_number_;
  // Reset packet count from congestion avoidance mode. We start counting again
  // when we're out of recovery.
  num_acked_packets_ = 0;
  QUIC_DVLOG(1) << "Incoming loss; congestion window: " << congestion_window_
                << " slowstart threshold: " << slowstart_threshold_;
}

QuicByteCount TcpMinervaSenderBytes::GetCongestionWindow() const {
  return congestion_window_;
}

QuicByteCount TcpMinervaSenderBytes::GetSlowStartThreshold() const {
  return slowstart_threshold_;
}

// Called when we receive an ack. Normal TCP tracks how many packets one ack
// represents, but quic has a separate ack for each packet.
void TcpMinervaSenderBytes::MaybeIncreaseCwnd(
    QuicPacketNumber /*acked_packet_number*/,
    QuicByteCount acked_bytes,
    QuicByteCount prior_in_flight,
    QuicTime event_time) {
  // Do not increase the congestion window unless the sender is close to using
  // the current window.
  if (!IsCwndLimited(prior_in_flight)) {
    cubic_.OnApplicationLimited();
    return;
  }
  if (congestion_window_ >= max_congestion_window_) {
    return;
  }
  
  if (InSlowStart()) {
    // TCP slow start, exponential growth, increase by one for each ACK.
    congestion_window_ += kDefaultTCPMSS;
    QUIC_DVLOG(1) << "Slow start; congestion window: " << congestion_window_
                  << " slowstart threshold: " << slowstart_threshold_;
    return;
  }
  
  // Congestion avoidance.
  congestion_window_ = std::min(
      max_congestion_window_,
      cubic_.CongestionWindowAfterAck(acked_bytes, congestion_window_,
                                      rtt_stats_->min_rtt(), event_time));
  
    QUIC_DVLOG(1) << "Cubic; congestion window: " << congestion_window_
                << " slowstart threshold: " << slowstart_threshold_;
}

void TcpMinervaSenderBytes::HandleRetransmissionTimeout() {
  cubic_.ResetCubicState();
  slowstart_threshold_ = congestion_window_ / 2;
  congestion_window_ = min_congestion_window_;
}

void TcpMinervaSenderBytes::OnConnectionMigration() {
  hybrid_slow_start_.Restart();
  prr_ = PrrSender();
  largest_sent_packet_number_.Clear();
  largest_acked_packet_number_.Clear();
  largest_sent_at_last_cutback_.Clear();
  last_cutback_exited_slowstart_ = false;
  cubic_.ResetCubicState();
  num_acked_packets_ = 0;
  congestion_window_ = initial_tcp_congestion_window_;
  max_congestion_window_ = initial_max_tcp_congestion_window_;
  slowstart_threshold_ = initial_max_tcp_congestion_window_;
}

CongestionControlType TcpMinervaSenderBytes::GetCongestionControlType() const {
  return kMinervaBytes; 
}

std::string TcpMinervaSenderBytes::GetDebugState() const { return ""; }
void TcpMinervaSenderBytes::OnApplicationLimited(QuicByteCount) {}
void TcpMinervaSenderBytes::SetFromConfig(const QuicConfig&, Perspective) {}

} 

#pragma GCC diagnostic pop

#include "net/abrcc/cc/gap.h"

#include <algorithm>
#include <sstream>
#include <string>

#include "net/third_party/quiche/src/quic/core/congestion_control/rtt_stats.h"
#include "net/third_party/quiche/src/quic/core/crypto/crypto_protocol.h"
#include "net/third_party/quiche/src/quic/core/quic_time.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_bug_tracker.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_fallthrough.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_flag_utils.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_flags.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

#include "net/abrcc/structs/estimators.h"
#include "net/abrcc/structs/averages.h"

#include "net/abrcc/cc/singleton.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_mutex.h"


#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Waddress-of-packed-member"


namespace quic {

namespace {
// Constants based on TCP defaults.
// The minimum CWND to ensure delayed acks don't reduce bandwidth measurements.
// Does not inflate the pacing rate.
const QuicByteCount kDefaultMinimumCongestionWindow = 4 * kMaxSegmentSize;

// The gain used for the STARTUP, equal to 2/ln(2).
const float kDefaultHighGain = 2.885f;
// The newly derived gain for STARTUP, equal to 4 * ln(2)
const float kDerivedHighGain = 2.773f;
// The newly derived CWND gain for STARTUP, 2.
const float kDerivedHighCWNDGain = 2.0f;
// The gain used in STARTUP after loss has been detected.
// 1.5 is enough to allow for 25% exogenous loss and still observe a 25% growth
// in measured bandwidth.
const float kStartupAfterLossGain = 1.5f;

// The time after which the current min_rtt value expires.
const QuicTime::Delta kMinRttExpiry = QuicTime::Delta::FromSeconds(10);
// The minimum time the connection can spend in PROBE_RTT mode.
const QuicTime::Delta kProbeRttTime = QuicTime::Delta::FromMilliseconds(200);
// If the bandwidth does not increase by the factor of |kStartupGrowthTarget|
// within |kRoundTripsWithoutGrowthBeforeExitingStartup| rounds, the connection
// will exit the STARTUP mode.
const float kStartupGrowthTarget = 1.25;
const QuicRoundTripCount kRoundTripsWithoutGrowthBeforeExitingStartup = 3;
// Coefficient of target congestion window to use when basing PROBE_RTT on BDP.
const float kModerateProbeRttMultiplier = 0.75;
// Coefficient to determine if a new RTT is sufficiently similar to min_rtt that
// we don't need to enter PROBE_RTT.
const float kSimilarMinRttThreshold = 1.125;

}  // namespace


/**
 * ABRCC Extension -- BEGIN
 **/

BbrGap::BbrInterface* BbrGap::BbrInterface::GetInstance() {
  return GET_SINGLETON(BbrGap::BbrInterface);
}

std::vector<float> BbrGap::BbrInterface::getPacingGainCycle() {
  return kPacingGain;
}

std::vector<int> BbrGap::BbrInterface::popDeliveryRates() {
  QuicWriterMutexLock lock(&delivery_rates_mutex_);
  std::vector<int> out = deliveryRates;
  deliveryRates = std::vector<int>();
  return out;
}

int BbrGap::BbrInterface::getGainCycleLength() {
  QuicReaderMutexLock lock(&pacing_cycle_mutex_);
  return kPacingGain.size();
}

QuicRoundTripCount BbrGap::BbrInterface::kBandwidthWindowSize() {
  return getGainCycleLength() + 2;
}

void BbrGap::BbrInterface::setParent(BbrGap *parent) {
  this->parent = parent;
}

bool BbrGap::BbrInterface::recovery() const {
  QuicReaderMutexLock lock(&recovery_mutex_);
  return recovery_;
}

void BbrGap::BbrInterface::setRecovery(bool recovery) {
  QuicWriterMutexLock lock(&recovery_mutex_);
  recovery_ = recovery; 
}

base::Optional<float> BbrGap::BbrInterface::PacingGain() const {
  QuicReaderMutexLock lock(&pacing_cycle_mutex_);
  if (parent == nullptr) {
    return base::nullopt;
  }
  return parent->pacing_gain_;
}

base::Optional<int> BbrGap::BbrInterface::getTargetRate() const { 
  QuicReaderMutexLock lock(&target_rate_mutex_);
  if (parent == nullptr) {
    return base::nullopt;
  }
  return targetRate;
}

void BbrGap::BbrInterface::setTargetRate(int rate) {
  QuicWriterMutexLock lock(&target_rate_mutex_);
  targetRate = rate;
}

base::Optional<int> BbrGap::BbrInterface::RttEstimate() const {
  if (parent == nullptr) {
    return base::nullopt;
  }
  return !parent->min_rtt_.IsZero() 
    ? base::Optional<int>(parent->min_rtt_.ToMilliseconds()) 
    : base::nullopt;
}

BbrGap::BbrInterface::BbrInterface() 
  : kPacingGain(std::vector<float>{1.25, 0.75, 1, 1, 1, 1, 1, 1})
  , deliveryRates(std::vector<int>{})
  , targetRate(base::nullopt)
  , parent(nullptr) {} 

BbrGap::BbrInterface::~BbrInterface() {}

void BbrGap::changeMode(BbrGap::Mode newMode) {
  QUIC_LOG(WARNING) << "[BBR Mode]: " << mode_ << " -> " << newMode;
  mode_ = newMode;
}

/**
 * ABRCC Extension -- END
 **/

BbrGap::DebugState::DebugState(const BbrGap& sender)
    : mode(sender.mode_),
      max_bandwidth(sender.max_bandwidth_.GetBest()),
      round_trip_count(sender.round_trip_count_),
      gain_cycle_index(sender.cycle_current_offset_),
      congestion_window(sender.congestion_window_),
      is_at_full_bandwidth(sender.is_at_full_bandwidth_),
      bandwidth_at_last_round(sender.bandwidth_at_last_round_),
      rounds_without_bandwidth_gain(sender.rounds_without_bandwidth_gain_),
      min_rtt(sender.min_rtt_),
      min_rtt_timestamp(sender.min_rtt_timestamp_),
      recovery_state(sender.recovery_state_),
      recovery_window(sender.recovery_window_),
      last_sample_is_app_limited(sender.last_sample_is_app_limited_),
      end_of_app_limited_phase(sender.sampler_.end_of_app_limited_phase()) {}

BbrGap::DebugState::DebugState(const DebugState& state) = default;

namespace BbrGapConstants {
  int bandwidth_estimator_window_size = 6;
  int bandwidth_estimator_p = 1;
  int bandwidth_estimator_i = 3;
  int bandwidth_estimator_d = 1;

  double scale_factor = .5;
}

BbrGap::BbrGap(QuicTime now,
                     const RttStats* rtt_stats,
                     const QuicUnackedPacketMap* unacked_packets,
                     QuicPacketCount initial_tcp_congestion_window,
                     QuicPacketCount max_tcp_congestion_window,
                     QuicRandom* random,
                     QuicConnectionStats* stats)
    : interface(BbrInterface::GetInstance()), 
      bandwidth_estimator(new structs::PIDEstimator<double>(
        BbrGapConstants::bandwidth_estimator_window_size, 
        BbrGapConstants::bandwidth_estimator_p,
        BbrGapConstants::bandwidth_estimator_i, 
        BbrGapConstants::bandwidth_estimator_d
      )), 

      rtt_stats_(rtt_stats),
      unacked_packets_(unacked_packets),
      random_(random),
      stats_(stats),
      mode_(STARTUP),
      sampler_(unacked_packets, BbrInterface::GetInstance()->kBandwidthWindowSize()),
      round_trip_count_(0),
      max_bandwidth_(BbrInterface::GetInstance()->kBandwidthWindowSize(), QuicBandwidth::Zero(), 0),
      min_rtt_(QuicTime::Delta::Zero()),
      min_rtt_timestamp_(QuicTime::Zero()),
      congestion_window_(initial_tcp_congestion_window * kDefaultTCPMSS),
      initial_congestion_window_(initial_tcp_congestion_window *
                                 kDefaultTCPMSS),
      max_congestion_window_(max_tcp_congestion_window * kDefaultTCPMSS),
      min_congestion_window_(kDefaultMinimumCongestionWindow),
      high_gain_(kDefaultHighGain),
      high_cwnd_gain_(kDefaultHighGain),
      drain_gain_(1.f / kDefaultHighGain),
      pacing_rate_(QuicBandwidth::Zero()),
      pacing_gain_(1),
      congestion_window_gain_(1),
      congestion_window_gain_constant_(
          static_cast<float>(GetQuicFlag(FLAGS_quic_bbr_cwnd_gain))),
      num_startup_rtts_(kRoundTripsWithoutGrowthBeforeExitingStartup),
      exit_startup_on_loss_(false),
      cycle_current_offset_(0),
      last_cycle_start_(QuicTime::Zero()),
      is_at_full_bandwidth_(false),
      rounds_without_bandwidth_gain_(0),
      bandwidth_at_last_round_(QuicBandwidth::Zero()),
      exiting_quiescence_(false),
      exit_probe_rtt_at_(QuicTime::Zero()),
      probe_rtt_round_passed_(false),
      last_sample_is_app_limited_(false),
      has_non_app_limited_sample_(false),
      flexible_app_limited_(false),
      recovery_state_(NOT_IN_RECOVERY),
      recovery_window_(max_congestion_window_),
      slower_startup_(false),
      rate_based_startup_(false),
      startup_rate_reduction_multiplier_(0),
      startup_bytes_lost_(0),
      enable_ack_aggregation_during_startup_(false),
      expire_ack_aggregation_in_startup_(false),
      drain_to_target_(false),
      probe_rtt_based_on_bdp_(false),
      probe_rtt_skipped_if_similar_rtt_(false),
      probe_rtt_disabled_if_app_limited_(false),
      app_limited_since_last_probe_rtt_(false),
      min_rtt_since_last_probe_rtt_(QuicTime::Delta::Infinite()) {
  if (stats_) {
    stats_->slowstart_count = 0;
    stats_->slowstart_start_time = QuicTime::Zero();
  }
  EnterStartupMode(now);
  interface->setParent(this);
}

BbrGap::~BbrGap() {
  if (interface->parent == this) {
    interface->setParent(nullptr);
  }
}

void BbrGap::SetInitialCongestionWindowInPackets(
    QuicPacketCount congestion_window) {
  if (mode_ == STARTUP) {
    initial_congestion_window_ = congestion_window * kDefaultTCPMSS;
    congestion_window_ = congestion_window * kDefaultTCPMSS;
  }
}

bool BbrGap::InSlowStart() const {
  return mode_ == STARTUP;
}

void BbrGap::OnPacketSent(QuicTime sent_time,
                             QuicByteCount bytes_in_flight,
                             QuicPacketNumber packet_number,
                             QuicByteCount bytes,
                             HasRetransmittableData is_retransmittable) {
  if (stats_ && InSlowStart()) {
    ++stats_->slowstart_packets_sent;
    stats_->slowstart_bytes_sent += bytes;
  }

  last_sent_packet_ = packet_number;

  if (bytes_in_flight == 0 && sampler_.is_app_limited()) {
    exiting_quiescence_ = true;
  }

  sampler_.OnPacketSent(sent_time, packet_number, bytes, bytes_in_flight,
                        is_retransmittable);
}

bool BbrGap::CanSend(QuicByteCount bytes_in_flight) {
  return bytes_in_flight < GetCongestionWindow();
}

QuicBandwidth BbrGap::PacingRate(QuicByteCount /*bytes_in_flight*/) const {
  if (pacing_rate_.IsZero()) {
    return high_gain_ * QuicBandwidth::FromBytesAndTimeDelta(
                            initial_congestion_window_, GetMinRtt());
  }
  return pacing_rate_;
}

QuicBandwidth BbrGap::BandwidthEstimate() const {
  return max_bandwidth_.GetBest();
}

QuicByteCount BbrGap::GetCongestionWindow() const {
  if (mode_ == PROBE_RTT) {
    return ProbeRttCongestionWindow();
  }

  if (InRecovery() && !(rate_based_startup_ && mode_ == STARTUP)) {
    return std::min(congestion_window_, recovery_window_);
  }

  return congestion_window_;
}

QuicByteCount BbrGap::GetSlowStartThreshold() const {
  return 0;
}

bool BbrGap::InRecovery() const {
  return recovery_state_ != NOT_IN_RECOVERY;
}

bool BbrGap::ShouldSendProbingPacket() const {
  if (pacing_gain_ <= 1) {
    return false;
  }

  // TODO(b/77975811): If the pipe is highly under-utilized, consider not
  // sending a probing transmission, because the extra bandwidth is not needed.
  // If flexible_app_limited is enabled, check if the pipe is sufficiently full.
  if (flexible_app_limited_) {
    return !IsPipeSufficientlyFull();
  } else {
    return true;
  }
}

bool BbrGap::IsPipeSufficientlyFull() const {
  // See if we need more bytes in flight to see more bandwidth.
  if (mode_ == STARTUP) {
    // STARTUP exits if it doesn't observe a 25% bandwidth increase, so the CWND
    // must be more than 25% above the target.
    return unacked_packets_->bytes_in_flight() >=
           GetTargetCongestionWindow(1.5);
  }
  if (pacing_gain_ > 1) {
    // Super-unity PROBE_BW doesn't exit until 1.25 * BDP is achieved.
    return unacked_packets_->bytes_in_flight() >=
           GetTargetCongestionWindow(pacing_gain_);
  }
  // If bytes_in_flight are above the target congestion window, it should be
  // possible to observe the same or more bandwidth if it's available.
  return unacked_packets_->bytes_in_flight() >= GetTargetCongestionWindow(1.1);
}

void BbrGap::SetFromConfig(const QuicConfig& config,
                              Perspective perspective) {
  if (config.HasClientRequestedIndependentOption(kLRTT, perspective)) {
    exit_startup_on_loss_ = true;
  }
  if (config.HasClientRequestedIndependentOption(k1RTT, perspective)) {
    num_startup_rtts_ = 1;
  }
  if (config.HasClientRequestedIndependentOption(k2RTT, perspective)) {
    num_startup_rtts_ = 2;
  }
  if (config.HasClientRequestedIndependentOption(kBBRS, perspective)) {
    slower_startup_ = true;
  }
  if (config.HasClientRequestedIndependentOption(kBBR3, perspective)) {
    drain_to_target_ = true;
  }
  if (config.HasClientRequestedIndependentOption(kBBS1, perspective)) {
    rate_based_startup_ = true;
  }
  if (GetQuicReloadableFlag(quic_bbr_startup_rate_reduction) &&
      config.HasClientRequestedIndependentOption(kBBS4, perspective)) {
    rate_based_startup_ = true;
    // Hits 1.25x pacing multiplier when ~2/3 CWND is lost.
    startup_rate_reduction_multiplier_ = 1;
  }
  if (GetQuicReloadableFlag(quic_bbr_startup_rate_reduction) &&
      config.HasClientRequestedIndependentOption(kBBS5, perspective)) {
    rate_based_startup_ = true;
    // Hits 1.25x pacing multiplier when ~1/3 CWND is lost.
    startup_rate_reduction_multiplier_ = 2;
  }
  if (config.HasClientRequestedIndependentOption(kBBR4, perspective)) {
    sampler_.SetMaxAckHeightTrackerWindowLength(2 * interface->kBandwidthWindowSize());
  }
  if (config.HasClientRequestedIndependentOption(kBBR5, perspective)) {
    sampler_.SetMaxAckHeightTrackerWindowLength(4 * interface->kBandwidthWindowSize());
  }
  if (GetQuicReloadableFlag(quic_bbr_less_probe_rtt) &&
      config.HasClientRequestedIndependentOption(kBBR6, perspective)) {
    QUIC_RELOADABLE_FLAG_COUNT_N(quic_bbr_less_probe_rtt, 1, 3);
    probe_rtt_based_on_bdp_ = true;
  }
  if (GetQuicReloadableFlag(quic_bbr_less_probe_rtt) &&
      config.HasClientRequestedIndependentOption(kBBR7, perspective)) {
    QUIC_RELOADABLE_FLAG_COUNT_N(quic_bbr_less_probe_rtt, 2, 3);
    probe_rtt_skipped_if_similar_rtt_ = true;
  }
  if (GetQuicReloadableFlag(quic_bbr_less_probe_rtt) &&
      config.HasClientRequestedIndependentOption(kBBR8, perspective)) {
    QUIC_RELOADABLE_FLAG_COUNT_N(quic_bbr_less_probe_rtt, 3, 3);
    probe_rtt_disabled_if_app_limited_ = true;
  }
  if (GetQuicReloadableFlag(quic_bbr_flexible_app_limited) &&
      config.HasClientRequestedIndependentOption(kBBR9, perspective)) {
    QUIC_RELOADABLE_FLAG_COUNT(quic_bbr_flexible_app_limited);
    flexible_app_limited_ = true;
  }
  if (config.HasClientRequestedIndependentOption(kBBQ1, perspective)) {
    set_high_gain(kDerivedHighGain);
    set_high_cwnd_gain(kDerivedHighGain);
    set_drain_gain(1.f / kDerivedHighGain);
  }
  if (config.HasClientRequestedIndependentOption(kBBQ2, perspective)) {
    set_high_cwnd_gain(kDerivedHighCWNDGain);
  }
  if (config.HasClientRequestedIndependentOption(kBBQ3, perspective)) {
    enable_ack_aggregation_during_startup_ = true;
  }
  if (GetQuicReloadableFlag(quic_bbr_slower_startup4) &&
      config.HasClientRequestedIndependentOption(kBBQ5, perspective)) {
    QUIC_RELOADABLE_FLAG_COUNT(quic_bbr_slower_startup4);
    expire_ack_aggregation_in_startup_ = true;
  }
  if (config.HasClientRequestedIndependentOption(kMIN1, perspective)) {
    min_congestion_window_ = kMaxSegmentSize;
  }
}

void BbrGap::AdjustNetworkParameters(const NetworkParams& params) {
  const QuicBandwidth& bandwidth = params.bandwidth;
  const QuicTime::Delta& rtt = params.rtt;

  if (GetQuicReloadableFlag(quic_bbr_donot_inject_bandwidth)) {
    QUIC_RELOADABLE_FLAG_COUNT(quic_bbr_donot_inject_bandwidth);
  } else if (!bandwidth.IsZero()) {
    max_bandwidth_.Update(bandwidth, round_trip_count_);
  }
  if (!rtt.IsZero() && (min_rtt_ > rtt || min_rtt_.IsZero())) {
    min_rtt_ = rtt;
  }

  if (params.quic_fix_bbr_cwnd_in_bandwidth_resumption && mode_ == STARTUP) {
    if (bandwidth.IsZero()) {
      // Ignore bad bandwidth samples.
      return;
    }
    const QuicByteCount new_cwnd = std::max(
        kMinInitialCongestionWindow * kDefaultTCPMSS,
        std::min(
            kMaxInitialCongestionWindow * kDefaultTCPMSS,
            bandwidth * (GetQuicReloadableFlag(quic_bbr_donot_inject_bandwidth)
                             ? GetMinRtt()
                             : rtt_stats_->SmoothedOrInitialRtt())));
    if (!rtt_stats_->smoothed_rtt().IsZero()) {
      QUIC_CODE_COUNT(quic_smoothed_rtt_available);
    } else if (rtt_stats_->initial_rtt() !=
               QuicTime::Delta::FromMilliseconds(kInitialRttMs)) {
      QUIC_CODE_COUNT(quic_client_initial_rtt_available);
    } else {
      QUIC_CODE_COUNT(quic_default_initial_rtt);
    }
    if (new_cwnd < congestion_window_ && !params.allow_cwnd_to_decrease) {
      // Only decrease cwnd if allow_cwnd_to_decrease is true.
      return;
    }
    if (GetQuicReloadableFlag(quic_conservative_cwnd_and_pacing_gains)) {
      // Decreases cwnd gain and pacing gain. Please note, if pacing_rate_ has
      // been calculated, it cannot decrease in STARTUP phase.
      QUIC_RELOADABLE_FLAG_COUNT(quic_conservative_cwnd_and_pacing_gains);
      set_high_gain(kDerivedHighCWNDGain);
      set_high_cwnd_gain(kDerivedHighCWNDGain);
    }
    congestion_window_ = new_cwnd;
    if (params.quic_bbr_fix_pacing_rate) {
      // Pace at the rate of new_cwnd / RTT.
      QuicBandwidth new_pacing_rate =
          QuicBandwidth::FromBytesAndTimeDelta(congestion_window_, GetMinRtt());
      pacing_rate_ = std::max(pacing_rate_, new_pacing_rate);
    }
  }
}

void BbrGap::OnCongestionEvent(bool /*rtt_updated*/,
                                  QuicByteCount prior_in_flight,
                                  QuicTime event_time,
                                  const AckedPacketVector& acked_packets,
                                  const LostPacketVector& lost_packets) {
  const QuicByteCount total_bytes_acked_before = sampler_.total_bytes_acked();

  bool is_round_start = false;
  bool min_rtt_expired = false;

  DiscardLostPackets(lost_packets);

  // Input the new data into the BBR model of the connection.
  QuicByteCount excess_acked = 0;
  if (!acked_packets.empty()) {
    QuicPacketNumber last_acked_packet = acked_packets.rbegin()->packet_number;
    is_round_start = UpdateRoundTripCounter(last_acked_packet);
    min_rtt_expired = UpdateBandwidthAndMinRtt(event_time, acked_packets);
    UpdateRecoveryState(last_acked_packet, !lost_packets.empty(),
                        is_round_start);

    excess_acked =
        sampler_.OnAckEventEnd(max_bandwidth_.GetBest(), round_trip_count_);
  }

  // Handle logic specific to PROBE_BW mode.
  if (mode_ == PROBE_BW) {
    UpdateGainCyclePhase(event_time, prior_in_flight, !lost_packets.empty());
  }

  // Handle logic specific to STARTUP and DRAIN modes.
  if (is_round_start && !is_at_full_bandwidth_) {
    CheckIfFullBandwidthReached();
  }
  MaybeExitStartupOrDrain(event_time);

  // Handle logic specific to PROBE_RTT.
  MaybeEnterOrExitProbeRtt(event_time, is_round_start, min_rtt_expired);

  // Calculate number of packets acked and lost.
  QuicByteCount bytes_acked =
      sampler_.total_bytes_acked() - total_bytes_acked_before;
  QuicByteCount bytes_lost = 0;
  for (const auto& packet : lost_packets) {
    bytes_lost += packet.bytes_lost;
  }

  // After the model is updated, recalculate the pacing rate and congestion
  // window.
  CalculatePacingRate();
  CalculateCongestionWindow(bytes_acked, excess_acked);
  CalculateRecoveryWindow(bytes_acked, bytes_lost);

  // Cleanup internal state.
  sampler_.RemoveObsoletePackets(unacked_packets_->GetLeastUnacked());
}

CongestionControlType BbrGap::GetCongestionControlType() const {
  return kAbbr;
}

QuicTime::Delta BbrGap::GetMinRtt() const {
  return !min_rtt_.IsZero() ? min_rtt_ : rtt_stats_->initial_rtt();
}

QuicByteCount BbrGap::GetTargetCongestionWindow(float gain) const {
  QuicByteCount bdp = GetMinRtt() * BandwidthEstimate();
  
  // [Gap] We modify this the Target received from the front-end
  auto maybe_target_bandwidth = interface->getTargetRate();
  if (maybe_target_bandwidth != base::nullopt) {
    auto target_bandwidth = quic::QuicBandwidth::FromKBitsPerSecond(
      (BandwidthEstimate().ToKBitsPerSecond() + maybe_target_bandwidth.value()) / 2
    );
    bdp = GetMinRtt() * target_bandwidth;
  }

  // [Startup] Compute the target congestion window without using future 
  // bandwidth estimators
  QuicByteCount current_congestion_window = bdp;
  if (mode_ == STARTUP) {
    current_congestion_window = bdp * gain;
  }
    
  // [No congestion window present] BDP estimate will be zero if no bandwidth samples are available yet.
  if (current_congestion_window == 0) {
    if (mode_ == STARTUP) {
      current_congestion_window = gain * initial_congestion_window_;
    } else {
      current_congestion_window = initial_congestion_window_;
    }
  }

  if (mode_ == STARTUP) {
    return std::max(current_congestion_window, min_congestion_window_);
  }

  // [Gap] use the future bandwidth estimator to change congestion window
  double bandwidth_estimator_ = bandwidth_estimator->value_or(0);
  
  // Handle now bandwidth estimator
  if (bandwidth_estimator_ == 0 || maybe_target_bandwidth == base::nullopt) {
    return std::max(current_congestion_window, min_congestion_window_);
  }

  // Use mean of future bandwidth estimator and current_congestion_window_
  auto potential_ = quic::QuicBandwidth::FromKBitsPerSecond((
    BandwidthEstimate().ToKBitsPerSecond() +
    bandwidth_estimator_
  ) / 2);

  // If the target bandwidth is bigger, weight towards it as potential. This means 
  // that we are more aggressive if we have a reason for it(by ABR) and our future 
  // estimator also predicts an increase in bandwidth.
  if (maybe_target_bandwidth.value() > BandwidthEstimate().ToKBitsPerSecond() && 
      maybe_target_bandwidth.value() > bandwidth_estimator_) {
    potential_ = quic::QuicBandwidth::FromKBitsPerSecond((
      BandwidthEstimate().ToKBitsPerSecond() +
      maybe_target_bandwidth.value() +
      bandwidth_estimator_
    ) / 3);
  }
  auto potential_window_ = GetMinRtt() * potential_;

  // Compute the windowed maximum and minium estimator trace values
  double min_estimator_trace = (double)(1 << 30);
  double max_estimator_trace = -(double)(1 << 30);
  int min_idx = 0;
  int max_idx = 0;
  for (int i = std::max(0, int(estimator_trace.size()) - 1 - BbrGapConstants::bandwidth_estimator_window_size);
      i < int(estimator_trace.size()); ++i) {
    if (estimator_trace[i] < min_estimator_trace) {
      min_estimator_trace = estimator_trace[i];
      min_idx = i;
    }
    if (estimator_trace[i] > max_estimator_trace) {
      max_estimator_trace = estimator_trace[i];
      max_idx = i;
    }
  }

  // If the estimator increased rapidly(e.g. 10 times) it may be that the bdp and rrt was increased, so we
  // are about to cause congestion, hence we should decrease the potential window 
  interface->setRecovery(false);
  double scale_factor = 1.;
  if (max_estimator_trace > 10 * min_estimator_trace && min_idx < max_idx) {
    //QUIC_LOG(WARNING) << "[GapCC] estimator trace large difference detected: " 
    //                  << min_estimator_trace << " -> " << max_estimator_trace;
    scale_factor = BbrGapConstants::scale_factor;
    interface->setRecovery(true);
  }
 
  //QUIC_LOG(WARNING) << "[GapCC] target bw: " << maybe_target_bandwidth.value();
  //QUIC_LOG(WARNING) << "[GapCC] bandwidth estimator: " << bandwidth_estimator_;
  //QUIC_LOG(WARNING) << "[GapCC] bdp current CW: " << current_congestion_window;
  //QUIC_LOG(WARNING) << "[GapCC] bdp potential: " << potential_window_;

  return std::max(scale_factor * std::max(current_congestion_window, potential_window_), 1. * min_congestion_window_);
}

QuicByteCount BbrGap::ProbeRttCongestionWindow() const {
  if (probe_rtt_based_on_bdp_) {
    return GetTargetCongestionWindow(kModerateProbeRttMultiplier);
  }
  return min_congestion_window_;
}

void BbrGap::EnterStartupMode(QuicTime now) {
  if (stats_) {
    ++stats_->slowstart_count;
    DCHECK_EQ(stats_->slowstart_start_time, QuicTime::Zero()) << mode_;
    stats_->slowstart_start_time = now;
  }
  changeMode(STARTUP);
  pacing_gain_ = high_gain_;
  congestion_window_gain_ = high_cwnd_gain_;
}

void BbrGap::EnterProbeBandwidthMode(QuicTime now) {
  changeMode(PROBE_BW);
  congestion_window_gain_ = congestion_window_gain_constant_;

  // Pick a random offset for the gain cycle out of {0, 2..7} range. 1 is
  // excluded because in that case increased gain and decreased gain would not
  // follow each other.
  cycle_current_offset_ = random_->RandUint64() % (interface->getGainCycleLength() - 1);
  if (cycle_current_offset_ >= 1) {
    cycle_current_offset_ += 1;
  }

  last_cycle_start_ = now;
  pacing_gain_ = interface->getPacingGainCycle()[cycle_current_offset_];
}

void BbrGap::DiscardLostPackets(const LostPacketVector& lost_packets) {
  for (const LostPacket& packet : lost_packets) {
    sampler_.OnPacketLost(packet.packet_number);
    if (mode_ == STARTUP) {
      if (stats_) {
        ++stats_->slowstart_packets_lost;
        stats_->slowstart_bytes_lost += packet.bytes_lost;
      }
      if (startup_rate_reduction_multiplier_ != 0) {
        startup_bytes_lost_ += packet.bytes_lost;
      }
    }
  }
}

bool BbrGap::UpdateRoundTripCounter(QuicPacketNumber last_acked_packet) {
  if (!current_round_trip_end_.IsInitialized() ||
      last_acked_packet > current_round_trip_end_) {
    round_trip_count_++;
    current_round_trip_end_ = last_sent_packet_;
    if (stats_ && InSlowStart()) {
      ++stats_->slowstart_num_rtts;
    }
    return true;
  }

  return false;
}

bool BbrGap::UpdateBandwidthAndMinRtt(
    QuicTime now,
    const AckedPacketVector& acked_packets) {
  // Use lock to register delivery rates
  QuicWriterMutexLock lock(&interface->delivery_rates_mutex_);
  
  QuicTime::Delta sample_min_rtt = QuicTime::Delta::Infinite();
  for (const auto& packet : acked_packets) {
    BandwidthSample bandwidth_sample =
        sampler_.OnPacketAcknowledged(now, packet.packet_number);
    if (!bandwidth_sample.state_at_send.is_valid) {
      // From the sampler's perspective, the packet has never been sent, or the
      // packet has been acked or marked as lost previously.
      continue;
    }

    // Register delivery rates
    interface->deliveryRates.push_back(
      bandwidth_sample.bandwidth.ToKBitsPerSecond()
    );

    last_sample_is_app_limited_ = bandwidth_sample.state_at_send.is_app_limited;
    has_non_app_limited_sample_ |=
        !bandwidth_sample.state_at_send.is_app_limited;
    if (!bandwidth_sample.rtt.IsZero()) {
      sample_min_rtt = std::min(sample_min_rtt, bandwidth_sample.rtt);
    }

    if (!bandwidth_sample.state_at_send.is_app_limited ||
        bandwidth_sample.bandwidth > BandwidthEstimate()) {
      max_bandwidth_.Update(bandwidth_sample.bandwidth, round_trip_count_);
    }
  }

  // If none of the RTT samples are valid, return immediately.
  if (sample_min_rtt.IsInfinite()) {
    return false;
  }
  min_rtt_since_last_probe_rtt_ =
      std::min(min_rtt_since_last_probe_rtt_, sample_min_rtt);

  // Do not expire min_rtt if none was ever available.
  bool min_rtt_expired =
      !min_rtt_.IsZero() && (now > (min_rtt_timestamp_ + kMinRttExpiry));

  if (min_rtt_expired || sample_min_rtt < min_rtt_ || min_rtt_.IsZero()) {
    QUIC_DVLOG(2) << "Min RTT updated, old value: " << min_rtt_
                  << ", new value: " << sample_min_rtt
                  << ", current time: " << now.ToDebuggingValue();

    if (min_rtt_expired && ShouldExtendMinRttExpiry()) {
      min_rtt_expired = false;
    } else {
      min_rtt_ = sample_min_rtt;
    }
    min_rtt_timestamp_ = now;
    // Reset since_last_probe_rtt fields.
    min_rtt_since_last_probe_rtt_ = QuicTime::Delta::Infinite();
    app_limited_since_last_probe_rtt_ = false;
  }
  DCHECK(!min_rtt_.IsZero());

  return min_rtt_expired;
}

bool BbrGap::ShouldExtendMinRttExpiry() const {
  if (probe_rtt_disabled_if_app_limited_ && app_limited_since_last_probe_rtt_) {
    // Extend the current min_rtt if we've been app limited recently.
    return true;
  }
  const bool min_rtt_increased_since_last_probe =
      min_rtt_since_last_probe_rtt_ > min_rtt_ * kSimilarMinRttThreshold;
  if (probe_rtt_skipped_if_similar_rtt_ && app_limited_since_last_probe_rtt_ &&
      !min_rtt_increased_since_last_probe) {
    // Extend the current min_rtt if we've been app limited recently and an rtt
    // has been measured in that time that's less than 12.5% more than the
    // current min_rtt.
    return true;
  }
  return false;
}


// [Gap] We modified the UpdateGainCyclePhase to add the estimators to our 
// future bandwidth estimator
void BbrGap::UpdateGainCyclePhase(
  QuicTime now,
  QuicByteCount prior_in_flight,
  bool has_losses
) {
  const QuicByteCount bytes_in_flight = unacked_packets_->bytes_in_flight();
  
  bool should_add_sample = now - last_cycle_start_ > GetMinRtt();
  if (bytes_in_flight <= GetTargetCongestionWindow(1)) {
    should_add_sample = true;
  }

  if (should_add_sample) {
    // [Gap] We are passing to a new paing gain cycle step, so we can register the old 
    // cycle
    bandwidth_estimator->sample(BandwidthEstimate().ToKBitsPerSecond()); 

    // Add to the estimator trace the bandwidth product, so we can observe abrupt changes 
    estimator_trace.push_back(BandwidthEstimate() * GetMinRtt());

    // we always use pacing_gain_ = 1
    pacing_gain_ = 1;
  }
}

void BbrGap::CheckIfFullBandwidthReached() {
  if (last_sample_is_app_limited_) {
    return;
  }

  QuicBandwidth target = bandwidth_at_last_round_ * kStartupGrowthTarget;
  if (BandwidthEstimate() >= target) {
    bandwidth_at_last_round_ = BandwidthEstimate();
    rounds_without_bandwidth_gain_ = 0;
    if (expire_ack_aggregation_in_startup_) {
      // Expire old excess delivery measurements now that bandwidth increased.
      sampler_.ResetMaxAckHeightTracker(0, round_trip_count_);
    }
    return;
  }

  rounds_without_bandwidth_gain_++;
  if ((rounds_without_bandwidth_gain_ >= num_startup_rtts_) ||
      (exit_startup_on_loss_ && InRecovery())) {
    DCHECK(has_non_app_limited_sample_);
    is_at_full_bandwidth_ = true;
  }
}

void BbrGap::MaybeExitStartupOrDrain(QuicTime now) {
  if (mode_ == STARTUP && is_at_full_bandwidth_) {
    OnExitStartup(now);
    changeMode(DRAIN);
    pacing_gain_ = drain_gain_;
    congestion_window_gain_ = high_cwnd_gain_;
  }
  if (mode_ == DRAIN &&
      unacked_packets_->bytes_in_flight() <= GetTargetCongestionWindow(1)) {
    EnterProbeBandwidthMode(now);
  }
}

void BbrGap::OnExitStartup(QuicTime now) {
  DCHECK_EQ(mode_, STARTUP);
  if (stats_) {
    DCHECK_NE(stats_->slowstart_start_time, QuicTime::Zero());
    if (now > stats_->slowstart_start_time) {
      stats_->slowstart_duration =
          now - stats_->slowstart_start_time + stats_->slowstart_duration;
    }
    stats_->slowstart_start_time = QuicTime::Zero();
  }
}

void BbrGap::MaybeEnterOrExitProbeRtt(QuicTime now,
                                         bool is_round_start,
                                         bool min_rtt_expired) {
  if (min_rtt_expired && !exiting_quiescence_ && mode_ != PROBE_RTT) {
    if (InSlowStart()) {
      OnExitStartup(now);
    }
    changeMode(PROBE_RTT);
    pacing_gain_ = 1;
    // Do not decide on the time to exit PROBE_RTT until the |bytes_in_flight|
    // is at the target small value.
    exit_probe_rtt_at_ = QuicTime::Zero();
  }

  if (mode_ == PROBE_RTT) {
    sampler_.OnAppLimited();

    if (exit_probe_rtt_at_ == QuicTime::Zero()) {
      // If the window has reached the appropriate size, schedule exiting
      // PROBE_RTT.  The CWND during PROBE_RTT is kMinimumCongestionWindow, but
      // we allow an extra packet since QUIC checks CWND before sending a
      // packet.
      if (unacked_packets_->bytes_in_flight() <
          ProbeRttCongestionWindow() + kMaxOutgoingPacketSize) {
        exit_probe_rtt_at_ = now + kProbeRttTime;
        probe_rtt_round_passed_ = false;
      }
    } else {
      if (is_round_start) {
        probe_rtt_round_passed_ = true;
      }
      if (now >= exit_probe_rtt_at_ && probe_rtt_round_passed_) {
        min_rtt_timestamp_ = now;
        if (!is_at_full_bandwidth_) {
          EnterStartupMode(now);
        } else {
          EnterProbeBandwidthMode(now);
        }
      }
    }
  }

  exiting_quiescence_ = false;
}

void BbrGap::UpdateRecoveryState(QuicPacketNumber last_acked_packet,
                                    bool has_losses,
                                    bool is_round_start) {
  // Exit recovery when there are no losses for a round.
  if (has_losses) {
    end_recovery_at_ = last_sent_packet_;
  }

  switch (recovery_state_) {
    case NOT_IN_RECOVERY:
      // Enter conservation on the first loss.
      if (has_losses) {
        recovery_state_ = CONSERVATION;
        // This will cause the |recovery_window_| to be set to the correct
        // value in CalculateRecoveryWindow().
        recovery_window_ = 0;
        // Since the conservation phase is meant to be lasting for a whole
        // round, extend the current round as if it were started right now.
        current_round_trip_end_ = last_sent_packet_;
      }
      break;

    case CONSERVATION:
      if (is_round_start) {
        recovery_state_ = GROWTH;
      }
      QUIC_FALLTHROUGH_INTENDED;

    case GROWTH:
      // Exit recovery if appropriate.
      if (!has_losses && last_acked_packet > end_recovery_at_) {
        recovery_state_ = NOT_IN_RECOVERY;
      }

      break;
  }
}

void BbrGap::CalculatePacingRate() {
  if (BandwidthEstimate().IsZero()) {
    return;
  }

  QuicBandwidth target_rate = pacing_gain_ * BandwidthEstimate();
  
  // [Target] Modify target_rate
  auto maybe_target_bandwidth = interface->getTargetRate();
  if (maybe_target_bandwidth != base::nullopt) {
    auto target_bandwidth = quic::QuicBandwidth::FromKBitsPerSecond(
      (BandwidthEstimate().ToKBitsPerSecond() + maybe_target_bandwidth.value()) / 2
    );
    target_rate = pacing_gain_ * target_bandwidth;
  }

  if (is_at_full_bandwidth_) {
    pacing_rate_ = target_rate;
    return;
  }

  // Pace at the rate of initial_window / RTT as soon as RTT measurements are
  // available.
  if (pacing_rate_.IsZero() && !rtt_stats_->min_rtt().IsZero()) {
    pacing_rate_ = QuicBandwidth::FromBytesAndTimeDelta(
        initial_congestion_window_, rtt_stats_->min_rtt());
    return;
  }
  // Slow the pacing rate in STARTUP once loss has ever been detected.
  const bool has_ever_detected_loss = end_recovery_at_.IsInitialized();
  if (slower_startup_ && has_ever_detected_loss &&
      has_non_app_limited_sample_) {
    pacing_rate_ = kStartupAfterLossGain * BandwidthEstimate();
    return;
  }

  // Slow the pacing rate in STARTUP by the bytes_lost / CWND.
  if (startup_rate_reduction_multiplier_ != 0 && has_ever_detected_loss &&
      has_non_app_limited_sample_) {
    pacing_rate_ =
        (1 - (startup_bytes_lost_ * startup_rate_reduction_multiplier_ * 1.0f /
              congestion_window_)) *
        target_rate;
    // Ensure the pacing rate doesn't drop below the startup growth target times
    // the bandwidth estimate.
    pacing_rate_ =
        std::max(pacing_rate_, kStartupGrowthTarget * BandwidthEstimate());
    return;
  }

  // Do not decrease the pacing rate during startup.
  pacing_rate_ = std::max(pacing_rate_, target_rate);
}

void BbrGap::CalculateCongestionWindow(QuicByteCount bytes_acked,
                                          QuicByteCount excess_acked) {
  if (mode_ == PROBE_RTT) {
    return;
  }

  QuicByteCount target_window =
      GetTargetCongestionWindow(congestion_window_gain_);
  if (is_at_full_bandwidth_) {
    // Add the max recently measured ack aggregation to CWND.
    target_window += sampler_.max_ack_height();
  } else if (enable_ack_aggregation_during_startup_) {
    // Add the most recent excess acked.  Because CWND never decreases in
    // STARTUP, this will automatically create a very localized max filter.
    target_window += excess_acked;
  }

  // Instead of immediately setting the target CWND as the new one, BBR grows
  // the CWND towards |target_window| by only increasing it |bytes_acked| at a
  // time.
  const bool add_bytes_acked =
      !GetQuicReloadableFlag(quic_bbr_no_bytes_acked_in_startup_recovery) ||
      !InRecovery();
  if (is_at_full_bandwidth_) {
    congestion_window_ =
        std::min(target_window, congestion_window_ + bytes_acked);
  } else if (add_bytes_acked &&
             (congestion_window_ < target_window ||
              sampler_.total_bytes_acked() < initial_congestion_window_)) {
    // If the connection is not yet out of startup phase, do not decrease the
    // window.
    congestion_window_ = congestion_window_ + bytes_acked;
  }

  // Enforce the limits on the congestion window.
  congestion_window_ = std::max(congestion_window_, min_congestion_window_);
  congestion_window_ = std::min(congestion_window_, max_congestion_window_);
}

void BbrGap::CalculateRecoveryWindow(QuicByteCount bytes_acked,
                                        QuicByteCount bytes_lost) {
  if (rate_based_startup_ && mode_ == STARTUP) {
    return;
  }

  if (recovery_state_ == NOT_IN_RECOVERY) {
    return;
  }

  // Set up the initial recovery window.
  if (recovery_window_ == 0) {
    recovery_window_ = unacked_packets_->bytes_in_flight() + bytes_acked;
    recovery_window_ = std::max(min_congestion_window_, recovery_window_);
    return;
  }

  // Remove losses from the recovery window, while accounting for a potential
  // integer underflow.
  recovery_window_ = recovery_window_ >= bytes_lost
                         ? recovery_window_ - bytes_lost
                         : kMaxSegmentSize;

  // In CONSERVATION mode, just subtracting losses is sufficient.  In GROWTH,
  // release additional |bytes_acked| to achieve a slow-start-like behavior.
  if (recovery_state_ == GROWTH) {
    recovery_window_ += bytes_acked;
  }

  // Sanity checks.  Ensure that we always allow to send at least an MSS or
  // |bytes_acked| in response, whichever is larger.
  recovery_window_ = std::max(
      recovery_window_, unacked_packets_->bytes_in_flight() + bytes_acked);
  if (GetQuicReloadableFlag(quic_bbr_one_mss_conservation)) {
    QUIC_RELOADABLE_FLAG_COUNT(quic_bbr_one_mss_conservation);
    recovery_window_ =
        std::max(recovery_window_,
                 unacked_packets_->bytes_in_flight() + kMaxSegmentSize);
  }
  recovery_window_ = std::max(min_congestion_window_, recovery_window_);
}

std::string BbrGap::GetDebugState() const {
  std::ostringstream stream;
  stream << ExportDebugState();
  return stream.str();
}

void BbrGap::OnApplicationLimited(QuicByteCount bytes_in_flight) {
  if (bytes_in_flight >= GetCongestionWindow()) {
    return;
  }
  if (flexible_app_limited_ && IsPipeSufficientlyFull()) {
    return;
  }

  app_limited_since_last_probe_rtt_ = true;
  sampler_.OnAppLimited();
  QUIC_DVLOG(2) << "Becoming application limited. Last sent packet: "
                << last_sent_packet_ << ", CWND: " << GetCongestionWindow();
}

BbrGap::DebugState BbrGap::ExportDebugState() const {
  return DebugState(*this);
}

static std::string ModeToString(BbrGap::Mode mode) {
  switch (mode) {
    case BbrGap::STARTUP:
      return "STARTUP";
    case BbrGap::DRAIN:
      return "DRAIN";
    case BbrGap::PROBE_BW:
      return "PROBE_BW";
    case BbrGap::PROBE_RTT:
      return "PROBE_RTT";
  }
  return "???";
}

std::ostream& operator<<(std::ostream& os, const BbrGap::Mode& mode) {
  os << ModeToString(mode);
  return os;
}

std::ostream& operator<<(std::ostream& os, const BbrGap::DebugState& state) {
  os << "Mode: " << ModeToString(state.mode) << std::endl;
  os << "Maximum bandwidth: " << state.max_bandwidth << std::endl;
  os << "Round trip counter: " << state.round_trip_count << std::endl;
  os << "Gain cycle index: " << static_cast<int>(state.gain_cycle_index)
     << std::endl;
  os << "Congestion window: " << state.congestion_window << " bytes"
     << std::endl;

  if (state.mode == BbrGap::STARTUP) {
    os << "(startup) Bandwidth at last round: " << state.bandwidth_at_last_round
       << std::endl;
    os << "(startup) Rounds without gain: "
       << state.rounds_without_bandwidth_gain << std::endl;
  }

  os << "Minimum RTT: " << state.min_rtt << std::endl;
  os << "Minimum RTT timestamp: " << state.min_rtt_timestamp.ToDebuggingValue()
     << std::endl;

  os << "Last sample is app-limited: "
     << (state.last_sample_is_app_limited ? "yes" : "no");

  return os;
}

}  // namespace quic

#pragma GCC diagnostic pop

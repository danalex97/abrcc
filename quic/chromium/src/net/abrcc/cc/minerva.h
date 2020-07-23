#ifndef ABRCC_CC_MINERVA_H_
#define ABRCC_CC_MINERVA_H_

#include <cstdint>
#include <string>

#include "net/third_party/quiche/src/quic/core/congestion_control/hybrid_slow_start.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/prr_sender.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/send_algorithm_interface.h"
#include "net/third_party/quiche/src/quic/core/quic_bandwidth.h"
#include "net/third_party/quiche/src/quic/core/quic_connection_stats.h"
#include "net/third_party/quiche/src/quic/core/quic_packets.h"
#include "net/third_party/quiche/src/quic/core/quic_time.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_export.h"

namespace quic {

class RttStats;

class QUIC_EXPORT_PRIVATE MinervaBytes {
 public:
  explicit MinervaBytes();
  MinervaBytes(const MinervaBytes&) = delete;
  MinervaBytes& operator=(const MinervaBytes&) = delete;

  void SetNumConnections(int num_connections);
  void ResetCubicState();

  QuicByteCount CongestionWindowAfterPacketLoss(QuicPacketCount current);
  QuicByteCount CongestionWindowAfterAck(QuicByteCount acked_bytes,
                                         QuicByteCount current,
                                         QuicTime::Delta delay_min,
                                         QuicTime event_time);
  void OnApplicationLimited();

 private:
  static const QuicTime::Delta MaxCubicTimeInterval() {
    return QuicTime::Delta::FromMilliseconds(30);
  }

  float Alpha() const;
  float Beta() const;
  float BetaLastMax() const;

  QuicByteCount last_max_congestion_window() const {
    return last_max_congestion_window_;
  }

  int num_connections_;

  QuicTime epoch_; // when cycle started
  QuicByteCount last_max_congestion_window_; // max CW before loss event
  QuicByteCount acked_bytes_count_; // acked bytes since epoch
  QuicByteCount estimated_tcp_congestion_window_; // CW in packets

  QuicByteCount origin_point_congestion_window_; // origin point of cubic func
  uint32_t time_to_origin_point_; // in 2^10 fraction of a second

  // Last congestion window in packets computed by cubic function.
  QuicByteCount last_target_congestion_window_;
};



class QUIC_EXPORT_PRIVATE TcpMinervaSenderBytes : public SendAlgorithmInterface {
 public:
  TcpMinervaSenderBytes(const RttStats* rtt_stats,
                      QuicPacketCount initial_tcp_congestion_window,
                      QuicPacketCount max_congestion_window,
                      QuicConnectionStats* stats);
  TcpMinervaSenderBytes(const TcpMinervaSenderBytes&) = delete;
  TcpMinervaSenderBytes& operator=(const TcpMinervaSenderBytes&) = delete;
  ~TcpMinervaSenderBytes() override;

  // Start implementation of SendAlgorithmInterface.
  void SetFromConfig(const QuicConfig& config,
                     Perspective perspective) override;
  void AdjustNetworkParameters(const NetworkParams& params) override;
  void SetNumEmulatedConnections(int num_connections);
  void SetInitialCongestionWindowInPackets(
      QuicPacketCount congestion_window) override;
  void OnConnectionMigration() override;
  void OnCongestionEvent(bool rtt_updated,
                         QuicByteCount prior_in_flight,
                         QuicTime event_time,
                         const AckedPacketVector& acked_packets,
                         const LostPacketVector& lost_packets) override;
  void OnPacketSent(QuicTime sent_time,
                    QuicByteCount bytes_in_flight,
                    QuicPacketNumber packet_number,
                    QuicByteCount bytes,
                    HasRetransmittableData is_retransmittable) override;
  void OnRetransmissionTimeout(bool packets_retransmitted) override;
  bool CanSend(QuicByteCount bytes_in_flight) override;
  QuicBandwidth PacingRate(QuicByteCount bytes_in_flight) const override;
  QuicBandwidth BandwidthEstimate() const override;
  QuicByteCount GetCongestionWindow() const override;
  QuicByteCount GetSlowStartThreshold() const override;
  CongestionControlType GetCongestionControlType() const override;
  bool InSlowStart() const override;
  bool InRecovery() const override;
  bool ShouldSendProbingPacket() const override;
  std::string GetDebugState() const override;
  void OnApplicationLimited(QuicByteCount bytes_in_flight) override;
  // End implementation of SendAlgorithmInterface.

  QuicByteCount min_congestion_window() const { return min_congestion_window_; }

 protected:
  float RenoBeta() const;

  bool IsCwndLimited(QuicByteCount bytes_in_flight) const;

  void OnPacketAcked(QuicPacketNumber acked_packet_number,
                     QuicByteCount acked_bytes,
                     QuicByteCount prior_in_flight,
                     QuicTime event_time);
  void SetCongestionWindowFromBandwidthAndRtt(QuicBandwidth bandwidth,
                                              QuicTime::Delta rtt);
  void SetMinCongestionWindowInPackets(QuicPacketCount congestion_window);
  void ExitSlowstart();
  void OnPacketLost(QuicPacketNumber largest_loss,
                    QuicByteCount lost_bytes,
                    QuicByteCount prior_in_flight);
  void MaybeIncreaseCwnd(QuicPacketNumber acked_packet_number,
                         QuicByteCount acked_bytes,
                         QuicByteCount prior_in_flight,
                         QuicTime event_time);
  void HandleRetransmissionTimeout();

 private:
  HybridSlowStart hybrid_slow_start_;
  PrrSender prr_;
  const RttStats* rtt_stats_;
  QuicConnectionStats* stats_;

  uint32_t num_connections_;

  QuicPacketNumber largest_sent_packet_number_;
  QuicPacketNumber largest_acked_packet_number_;
  QuicPacketNumber largest_sent_at_last_cutback_;
  
  bool min4_mode_;
  bool last_cutback_exited_slowstart_;
  bool slow_start_large_reduction_;

  MinervaBytes cubic_;
  uint64_t num_acked_packets_;

  QuicByteCount congestion_window_;
  QuicByteCount min_congestion_window_;
  QuicByteCount max_congestion_window_;
  QuicByteCount slowstart_threshold_;

  const QuicByteCount initial_tcp_congestion_window_;
  const QuicByteCount initial_max_tcp_congestion_window_;
  QuicByteCount min_slow_start_exit_window_;
};

}  // namespace quic

#endif  

#ifndef ABRCC_CC_WRAPPER_H_
#define ABRCC_CC_WRAPPER_H_

#include "net/third_party/quiche/src/quic/core/congestion_control/bandwidth_sampler.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/bbr2_drain.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/bbr2_misc.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/bbr2_probe_bw.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/bbr2_probe_rtt.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/bbr2_startup.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/rtt_stats.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/send_algorithm_interface.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/windowed_filter.h"
#include "net/third_party/quiche/src/quic/core/quic_bandwidth.h"
#include "net/third_party/quiche/src/quic/core/quic_types.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_export.h"

namespace quic {

class CCWrapper : public SendAlgorithmInterface { 
 public:
  CCWrapper(SendAlgorithmInterface* interface);
  ~CCWrapper() override;

  void SetFromConfig(const QuicConfig& config, Perspective perspective) override;
  void SetInitialCongestionWindowInPackets(QuicPacketCount packets) override;
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
  void OnConnectionMigration() override;
  bool CanSend(QuicByteCount bytes_in_flight) override;
  QuicBandwidth PacingRate(QuicByteCount bytes_in_flight) const override;
  QuicBandwidth BandwidthEstimate() const override;
  QuicByteCount GetCongestionWindow() const override;
  bool InSlowStart() const override;
  bool InRecovery() const override;
  bool ShouldSendProbingPacket() const override;
  QuicByteCount GetSlowStartThreshold() const override;
  CongestionControlType GetCongestionControlType() const override;
  void AdjustNetworkParameters(const NetworkParams& params) override;
  std::string GetDebugState() const override;
  void OnApplicationLimited(QuicByteCount bytes_in_flight) override;
 private:
  SendAlgorithmInterface* interface;
};

}

#endif

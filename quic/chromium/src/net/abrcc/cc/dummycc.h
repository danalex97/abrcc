#ifndef ABRCC_CC_DUMMYCC_H_
#define ABRCC_CC_DUMMYCC_H_

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

class DummySender : public SendAlgorithmInterface { 
 public:
  DummySender();
  ~DummySender() override;

  void SetFromConfig(const QuicConfig& config, Perspective perspective) override;

  // Sets the initial congestion window in number of packets. 
  void SetInitialCongestionWindowInPackets(QuicPacketCount packets) override;

  // Indicates an update to the congestion state, caused either by an incoming
  // ack or loss event timeout.  
  //   |rtt_updated| indicates whether a new latest_rtt sample has been taken
  //   |prior_in_flight| the bytes in flight prior to the congestion event
  //   |acked_packets| and |lost_packets| are any packets considered acked 
  //                  or lost as a result of the congestion event.
  void OnCongestionEvent(bool rtt_updated,
                         QuicByteCount prior_in_flight,
                         QuicTime event_time,
                         const AckedPacketVector& acked_packets,
                         const LostPacketVector& lost_packets) override;

  // Inform that we sent 
  //   |bytes| to the wire, and if the packet is retransmittable
  //   |bytes_in_flight| is the number of bytes in flight before the packet was sent.
  void OnPacketSent(QuicTime sent_time,
                    QuicByteCount bytes_in_flight,
                    QuicPacketNumber packet_number,
                    QuicByteCount bytes,
                    HasRetransmittableData is_retransmittable) override;

  // Called when the retransmission timeout fires.  Neither OnPacketAbandoned
  // nor OnPacketLost will be called for these packets.
  void OnRetransmissionTimeout(bool packets_retransmitted) override;

  // Called when connection migrates and cwnd needs to be reset.
  void OnConnectionMigration() override;

  // Make decision on whether the sender can send right now.  Note that even
  // when this method returns true, the sending can be delayed due to pacing.
  bool CanSend(QuicByteCount bytes_in_flight) override;

  // The pacing rate of the send algorithm.  May be zero if the rate is unknown.
  QuicBandwidth PacingRate(QuicByteCount bytes_in_flight) const override;

  // What's the current estimated bandwidth in bytes per second.
  // Returns 0 when it does not have an estimate.
  QuicBandwidth BandwidthEstimate() const override;

  // Returns the size of the current congestion window in bytes.  Note, this is
  // not the *available* window.  Some send algorithms may not use a congestion
  // window and will return 0.
  QuicByteCount GetCongestionWindow() const override;

  // Whether the send algorithm is currently in slow start.  When true, the
  // BandwidthEstimate is expected to be too low.
  bool InSlowStart() const override;

  // Whether the send algorithm is currently in recovery.
  bool InRecovery() const override;

  // True when the congestion control is probing for more bandwidth and needs
  // enough data to not be app-limited to do so.
  bool ShouldSendProbingPacket() const override;

  // Returns the size of the slow start congestion window in bytes,
  // aka ssthresh.  Only defined for Cubic and Reno, other algorithms return 0.
  QuicByteCount GetSlowStartThreshold() const override;

  CongestionControlType GetCongestionControlType() const override;

  // Notifies the congestion control algorithm of an external network
  // measurement or prediction.  Either |bandwidth| or |rtt| may be zero if no
  // sample is available.
  void AdjustNetworkParameters(const NetworkParams& params) override;

  // Retrieves debugging information about the current state of the
  // send algorithm.
  std::string GetDebugState() const override;

  // Called when the connection has no outstanding data to send. Specifically,
  // this means that none of the data streams are write-blocked, there are no
  // packets in the connection queue, and there are no pending retransmissins,
  // i.e. the sender cannot send anything for reasons other than being blocked
  // by congestion controller. This includes cases when the connection is
  // blocked by the flow controller.
  //
  // The fact that this method is called does not necessarily imply that the
  // connection would not be blocked by the congestion control if it actually
  // tried to send data. If the congestion control algorithm needs to exclude
  // such cases, it should use the internal state it uses for congestion control
  // for that.
  void OnApplicationLimited(QuicByteCount bytes_in_flight) override;
};

}

#endif

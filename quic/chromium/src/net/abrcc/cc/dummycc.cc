#include "net/abrcc/cc/dummycc.h"

namespace quic {

DummySender::DummySender() {
}

DummySender::~DummySender() {
}


void DummySender::SetFromConfig(const QuicConfig& config, Perspective perspective) {
}

 
void DummySender::SetInitialCongestionWindowInPackets(QuicPacketCount packets) {
}


void DummySender::OnCongestionEvent(
  bool rtt_updated,
  QuicByteCount prior_in_flight,
  QuicTime event_time,
  const AckedPacketVector& acked_packets,
  const LostPacketVector& lost_packets
) {
}


void DummySender::OnPacketSent(
  QuicTime sent_time,
  QuicByteCount bytes_in_flight,
  QuicPacketNumber packet_number,
  QuicByteCount bytes,
  HasRetransmittableData is_retransmittable
) {
}


void DummySender::OnRetransmissionTimeout(bool packets_retransmitted) {
}


void DummySender::OnConnectionMigration() {
}


bool DummySender::CanSend(QuicByteCount bytes_in_flight) {
  return true;
}


QuicBandwidth DummySender::PacingRate(QuicByteCount bytes_in_flight) const {
  return QuicBandwidth::Zero();   
}


QuicBandwidth DummySender::BandwidthEstimate() const {
  return QuicBandwidth::Zero();
}

QuicByteCount DummySender::GetCongestionWindow() const {
  return QuicByteCount(0);
}


bool DummySender::InSlowStart() const {
  return false;
}


bool DummySender::InRecovery() const {
  return false;
}


bool DummySender::ShouldSendProbingPacket() const {
  return false;
}

QuicByteCount DummySender::GetSlowStartThreshold() const {
  return QuicByteCount(0);
}

CongestionControlType DummySender::GetCongestionControlType() const {
  return kDummy;  
}

  
void DummySender::AdjustNetworkParameters(const NetworkParams& params) {
}


std::string DummySender::GetDebugState() const {
  return "";
}

void DummySender::OnApplicationLimited(QuicByteCount bytes_in_flight) {
}

}

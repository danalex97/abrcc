#include "net/abrcc/cc/cc_wrapper.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

namespace quic {

CCWrapper::CCWrapper(SendAlgorithmInterface* interface) : interface(interface) {}
CCWrapper::~CCWrapper() { }

void CCWrapper::SetFromConfig(const QuicConfig& config, Perspective perspective) {
  interface->SetFromConfig(config, perspective);
}

void CCWrapper::SetInitialCongestionWindowInPackets(QuicPacketCount packets) {
  interface->SetInitialCongestionWindowInPackets(packets);
}


void CCWrapper::OnCongestionEvent(
  bool rtt_updated,
  QuicByteCount prior_in_flight,
  QuicTime event_time,
  const AckedPacketVector& acked_packets,
  const LostPacketVector& lost_packets
) {
  interface->OnCongestionEvent(rtt_updated, prior_in_flight, event_time, acked_packets, lost_packets);
}


void CCWrapper::OnPacketSent(
  QuicTime sent_time,
  QuicByteCount bytes_in_flight,
  QuicPacketNumber packet_number,
  QuicByteCount bytes,
  HasRetransmittableData is_retransmittable
) {
  interface->OnPacketSent(sent_time, bytes_in_flight, packet_number, bytes, is_retransmittable); 
}


void CCWrapper::OnRetransmissionTimeout(bool packets_retransmitted) {
  interface->OnRetransmissionTimeout(packets_retransmitted); 
}


void CCWrapper::OnConnectionMigration() {
  interface->OnConnectionMigration();
}


bool CCWrapper::CanSend(QuicByteCount bytes_in_flight) {
  return interface->CanSend(bytes_in_flight);
}


QuicBandwidth CCWrapper::PacingRate(QuicByteCount bytes_in_flight) const {
  return interface->PacingRate(bytes_in_flight); 
}


QuicBandwidth CCWrapper::BandwidthEstimate() const {
  return interface->BandwidthEstimate();
}

QuicByteCount CCWrapper::GetCongestionWindow() const {
  return interface->GetCongestionWindow();
}

bool CCWrapper::InSlowStart() const {
  return interface->InSlowStart();
}

bool CCWrapper::InRecovery() const {
  return interface->InRecovery();
}

bool CCWrapper::ShouldSendProbingPacket() const {
  return interface->ShouldSendProbingPacket();
}

QuicByteCount CCWrapper::GetSlowStartThreshold() const {
  return interface->GetSlowStartThreshold();
}

CongestionControlType CCWrapper::GetCongestionControlType() const {
  return interface->GetCongestionControlType();  
}

void CCWrapper::AdjustNetworkParameters(const NetworkParams& params) {
  interface->AdjustNetworkParameters(params);
}

std::string CCWrapper::GetDebugState() const {
  return interface->GetDebugState();
}

void CCWrapper::OnApplicationLimited(QuicByteCount bytes_in_flight) {
  interface->OnApplicationLimited(bytes_in_flight);
}

}

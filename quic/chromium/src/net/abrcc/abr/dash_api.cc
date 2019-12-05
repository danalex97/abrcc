#include "net/abrcc/abr/dash_api.h"
#include "net/abrcc/abr/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_text_utils.h"

#include "base/json/json_value_converter.h"
#include "base/json/json_reader.h"
#include "base/json/json_writer.h"
#include "base/values.h"

using namespace abr_schema;
using spdy::SpdyHeaderBlock;

namespace quic {

DashApi::DashApi(std::unique_ptr<AbrInterface> abr) : abr(std::move(abr)) {}
DashApi::~DashApi() {}

void DashApi::FetchResponseFromBackend(
  const SpdyHeaderBlock& request_headers,
  const std::string& data, 
  QuicSimpleServerBackend::RequestHandler* quic_stream
) {
  DashRequest request;
   
  base::Optional<base::Value> value = base::JSONReader::Read(data);
  base::JSONValueConverter<DashRequest> converter;
  converter.Convert(*value, &request);
  
  abr->registerMetrics(request.metrics);  
  if (request.piggyback) {
    Decision decision = abr->decide();
    std::string body = decision.serialize();
  
    SpdyHeaderBlock response_headers;
    response_headers[":status"] = QuicTextUtils::Uint64ToString(200);
    response_headers["content-length"] = QuicTextUtils::Uint64ToString(body.length());
    
    auto* quic_response = new QuicBackendResponse(); 
    quic_response->set_response_type(QuicBackendResponse::REGULAR_RESPONSE);
    quic_response->set_headers(std::move(response_headers));
    quic_response->set_body(body);
    quic_response->set_trailers(SpdyHeaderBlock());
    quic_response->set_stop_sending_code(0);

    auto push_info = std::list<QuicBackendResponse::ServerPushInfo>();
    quic_stream->OnResponseBackendComplete(quic_response, push_info); 
  }
}

}

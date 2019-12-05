#include "net/abrcc/abr/dash_api.h"
#include "net/abrcc/abr/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

#include "base/json/json_value_converter.h"
#include "base/json/json_reader.h"
#include "base/values.h"

using namespace abr_schema;
using spdy::SpdyHeaderBlock;

namespace quic {

DashApi::DashApi() {}
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
  
  registerMetrics(request.metrics);  
  if (request.piggyback) {
    // [TODO]
  }
}

void DashApi::registerMetrics(const Metrics &metrics) {
  // [TODO]
}

}

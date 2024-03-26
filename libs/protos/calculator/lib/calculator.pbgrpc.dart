///
//  Generated code. Do not modify.
//  source: calculator.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:async' as $async;

import 'dart:core' as $core;

import 'package:grpc/service_api.dart' as $grpc;
import 'calculator.pb.dart' as $0;
export 'calculator.pb.dart';

class CalculatorClient extends $grpc.Client {
  static final _$addIntegers =
      $grpc.ClientMethod<$0.AddIntegersRequest, $0.AddIntegersResponse>(
          '/Calculator/AddIntegers',
          ($0.AddIntegersRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.AddIntegersResponse.fromBuffer(value));

  CalculatorClient($grpc.ClientChannel channel,
      {$grpc.CallOptions? options,
      $core.Iterable<$grpc.ClientInterceptor>? interceptors})
      : super(channel, options: options, interceptors: interceptors);

  $grpc.ResponseFuture<$0.AddIntegersResponse> addIntegers(
      $0.AddIntegersRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$addIntegers, request, options: options);
  }
}

abstract class CalculatorServiceBase extends $grpc.Service {
  $core.String get $name => 'Calculator';

  CalculatorServiceBase() {
    $addMethod(
        $grpc.ServiceMethod<$0.AddIntegersRequest, $0.AddIntegersResponse>(
            'AddIntegers',
            addIntegers_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.AddIntegersRequest.fromBuffer(value),
            ($0.AddIntegersResponse value) => value.writeToBuffer()));
  }

  $async.Future<$0.AddIntegersResponse> addIntegers_Pre($grpc.ServiceCall call,
      $async.Future<$0.AddIntegersRequest> request) async {
    return addIntegers(call, await request);
  }

  $async.Future<$0.AddIntegersResponse> addIntegers(
      $grpc.ServiceCall call, $0.AddIntegersRequest request);
}

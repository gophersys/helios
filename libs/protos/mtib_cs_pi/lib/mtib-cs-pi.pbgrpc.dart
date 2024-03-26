///
//  Generated code. Do not modify.
//  source: mtib-cs-pi.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:async' as $async;

import 'dart:core' as $core;

import 'package:grpc/service_api.dart' as $grpc;
import 'mtib-cs-pi.pb.dart' as $0;
export 'mtib-cs-pi.pb.dart';

class MtibCsPiClient extends $grpc.Client {
  static final _$healthCheck =
      $grpc.ClientMethod<$0.HealthCheckRequest, $0.HealthCheckResponse>(
          '/MtibCsPi/HealthCheck',
          ($0.HealthCheckRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.HealthCheckResponse.fromBuffer(value));
  static final _$gpioConfig =
      $grpc.ClientMethod<$0.GpioConfigRequest, $0.GpioConfigResponse>(
          '/MtibCsPi/GpioConfig',
          ($0.GpioConfigRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.GpioConfigResponse.fromBuffer(value));
  static final _$gpioWrite =
      $grpc.ClientMethod<$0.GpioWriteRequest, $0.GpioWriteResponse>(
          '/MtibCsPi/GpioWrite',
          ($0.GpioWriteRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.GpioWriteResponse.fromBuffer(value));
  static final _$gpioRead =
      $grpc.ClientMethod<$0.GpioReadRequest, $0.GpioReadResponse>(
          '/MtibCsPi/GpioRead',
          ($0.GpioReadRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.GpioReadResponse.fromBuffer(value));
  static final _$adcRead =
      $grpc.ClientMethod<$0.AdcReadRequest, $0.AdcReadResponse>(
          '/MtibCsPi/AdcRead',
          ($0.AdcReadRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.AdcReadResponse.fromBuffer(value));
  static final _$adcReadAll =
      $grpc.ClientMethod<$0.AdcReadAllRequest, $0.AdcReadAllResponse>(
          '/MtibCsPi/AdcReadAll',
          ($0.AdcReadAllRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.AdcReadAllResponse.fromBuffer(value));
  static final _$dutPowerEnable =
      $grpc.ClientMethod<$0.DutPowerEnableRequest, $0.DutPowerEnableResponse>(
          '/MtibCsPi/DutPowerEnable',
          ($0.DutPowerEnableRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.DutPowerEnableResponse.fromBuffer(value));
  static final _$dutChargePowerEnable =
      $grpc.ClientMethod<$0.DutPowerEnableRequest, $0.DutPowerEnableResponse>(
          '/MtibCsPi/DutChargePowerEnable',
          ($0.DutPowerEnableRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.DutPowerEnableResponse.fromBuffer(value));
  static final _$dutVoltageSet =
      $grpc.ClientMethod<$0.DutVoltageSetRequest, $0.DutVoltageSetResponse>(
          '/MtibCsPi/DutVoltageSet',
          ($0.DutVoltageSetRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.DutVoltageSetResponse.fromBuffer(value));
  static final _$dutCurrentRead =
      $grpc.ClientMethod<$0.DutCurrentReadRequest, $0.DutCurrentReadResponse>(
          '/MtibCsPi/DutCurrentRead',
          ($0.DutCurrentReadRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.DutCurrentReadResponse.fromBuffer(value));
  static final _$dutVoltageRead =
      $grpc.ClientMethod<$0.DutVoltageReadRequest, $0.DutVoltageReadResponse>(
          '/MtibCsPi/DutVoltageRead',
          ($0.DutVoltageReadRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.DutVoltageReadResponse.fromBuffer(value));
  static final _$dutPowerRead =
      $grpc.ClientMethod<$0.DutPowerReadRequest, $0.DutPowerReadResponse>(
          '/MtibCsPi/DutPowerRead',
          ($0.DutPowerReadRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.DutPowerReadResponse.fromBuffer(value));
  static final _$altimeterRead =
      $grpc.ClientMethod<$0.AltimeterReadRequest, $0.AltimeterReadResponse>(
          '/MtibCsPi/AltimeterRead',
          ($0.AltimeterReadRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.AltimeterReadResponse.fromBuffer(value));
  static final _$accelRead =
      $grpc.ClientMethod<$0.AccelReadRequest, $0.AccelReadResponse>(
          '/MtibCsPi/AccelRead',
          ($0.AccelReadRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.AccelReadResponse.fromBuffer(value));
  static final _$accelReadMaxForce =
      $grpc.ClientMethod<$0.AccelReadMaxRequest, $0.AccelReadMaxResponse>(
          '/MtibCsPi/AccelReadMaxForce',
          ($0.AccelReadMaxRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.AccelReadMaxResponse.fromBuffer(value));
  static final _$eepromRead =
      $grpc.ClientMethod<$0.EepromReadRequest, $0.EepromReadResponse>(
          '/MtibCsPi/EepromRead',
          ($0.EepromReadRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.EepromReadResponse.fromBuffer(value));
  static final _$eepromWrite =
      $grpc.ClientMethod<$0.EepromWriteRequest, $0.EepromWriteResponse>(
          '/MtibCsPi/EepromWrite',
          ($0.EepromWriteRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.EepromWriteResponse.fromBuffer(value));
  static final _$listFwFiles =
      $grpc.ClientMethod<$0.ListFwFilesRequest, $0.ListFwFilesResponse>(
          '/MtibCsPi/ListFwFiles',
          ($0.ListFwFilesRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.ListFwFilesResponse.fromBuffer(value));
  static final _$uploadFwFile =
      $grpc.ClientMethod<$0.UploadFwFileRequest, $0.UploadFwFileResponse>(
          '/MtibCsPi/UploadFwFile',
          ($0.UploadFwFileRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.UploadFwFileResponse.fromBuffer(value));
  static final _$deleteFwFile =
      $grpc.ClientMethod<$0.DeleteFwFileRequest, $0.DeleteFwFileResponse>(
          '/MtibCsPi/DeleteFwFile',
          ($0.DeleteFwFileRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.DeleteFwFileResponse.fromBuffer(value));
  static final _$flashHexFile =
      $grpc.ClientMethod<$0.FlashHexFileRequest, $0.FlashHexFileResponse>(
          '/MtibCsPi/FlashHexFile',
          ($0.FlashHexFileRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.FlashHexFileResponse.fromBuffer(value));

  MtibCsPiClient($grpc.ClientChannel channel,
      {$grpc.CallOptions? options,
      $core.Iterable<$grpc.ClientInterceptor>? interceptors})
      : super(channel, options: options, interceptors: interceptors);

  $grpc.ResponseFuture<$0.HealthCheckResponse> healthCheck(
      $0.HealthCheckRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$healthCheck, request, options: options);
  }

  $grpc.ResponseFuture<$0.GpioConfigResponse> gpioConfig(
      $0.GpioConfigRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$gpioConfig, request, options: options);
  }

  $grpc.ResponseFuture<$0.GpioWriteResponse> gpioWrite(
      $0.GpioWriteRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$gpioWrite, request, options: options);
  }

  $grpc.ResponseFuture<$0.GpioReadResponse> gpioRead($0.GpioReadRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$gpioRead, request, options: options);
  }

  $grpc.ResponseFuture<$0.AdcReadResponse> adcRead($0.AdcReadRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$adcRead, request, options: options);
  }

  $grpc.ResponseFuture<$0.AdcReadAllResponse> adcReadAll(
      $0.AdcReadAllRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$adcReadAll, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutPowerEnableResponse> dutPowerEnable(
      $0.DutPowerEnableRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutPowerEnable, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutPowerEnableResponse> dutChargePowerEnable(
      $0.DutPowerEnableRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutChargePowerEnable, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutVoltageSetResponse> dutVoltageSet(
      $0.DutVoltageSetRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutVoltageSet, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutCurrentReadResponse> dutCurrentRead(
      $0.DutCurrentReadRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutCurrentRead, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutVoltageReadResponse> dutVoltageRead(
      $0.DutVoltageReadRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutVoltageRead, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutPowerReadResponse> dutPowerRead(
      $0.DutPowerReadRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutPowerRead, request, options: options);
  }

  $grpc.ResponseFuture<$0.AltimeterReadResponse> altimeterRead(
      $0.AltimeterReadRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$altimeterRead, request, options: options);
  }

  $grpc.ResponseFuture<$0.AccelReadResponse> accelRead(
      $0.AccelReadRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$accelRead, request, options: options);
  }

  $grpc.ResponseFuture<$0.AccelReadMaxResponse> accelReadMaxForce(
      $0.AccelReadMaxRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$accelReadMaxForce, request, options: options);
  }

  $grpc.ResponseFuture<$0.EepromReadResponse> eepromRead(
      $0.EepromReadRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$eepromRead, request, options: options);
  }

  $grpc.ResponseFuture<$0.EepromWriteResponse> eepromWrite(
      $0.EepromWriteRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$eepromWrite, request, options: options);
  }

  $grpc.ResponseFuture<$0.ListFwFilesResponse> listFwFiles(
      $0.ListFwFilesRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$listFwFiles, request, options: options);
  }

  $grpc.ResponseFuture<$0.UploadFwFileResponse> uploadFwFile(
      $async.Stream<$0.UploadFwFileRequest> request,
      {$grpc.CallOptions? options}) {
    return $createStreamingCall(_$uploadFwFile, request, options: options)
        .single;
  }

  $grpc.ResponseFuture<$0.DeleteFwFileResponse> deleteFwFile(
      $0.DeleteFwFileRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$deleteFwFile, request, options: options);
  }

  $grpc.ResponseFuture<$0.FlashHexFileResponse> flashHexFile(
      $0.FlashHexFileRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$flashHexFile, request, options: options);
  }
}

abstract class MtibCsPiServiceBase extends $grpc.Service {
  $core.String get $name => 'MtibCsPi';

  MtibCsPiServiceBase() {
    $addMethod(
        $grpc.ServiceMethod<$0.HealthCheckRequest, $0.HealthCheckResponse>(
            'HealthCheck',
            healthCheck_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.HealthCheckRequest.fromBuffer(value),
            ($0.HealthCheckResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.GpioConfigRequest, $0.GpioConfigResponse>(
        'GpioConfig',
        gpioConfig_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.GpioConfigRequest.fromBuffer(value),
        ($0.GpioConfigResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.GpioWriteRequest, $0.GpioWriteResponse>(
        'GpioWrite',
        gpioWrite_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.GpioWriteRequest.fromBuffer(value),
        ($0.GpioWriteResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.GpioReadRequest, $0.GpioReadResponse>(
        'GpioRead',
        gpioRead_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.GpioReadRequest.fromBuffer(value),
        ($0.GpioReadResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.AdcReadRequest, $0.AdcReadResponse>(
        'AdcRead',
        adcRead_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.AdcReadRequest.fromBuffer(value),
        ($0.AdcReadResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.AdcReadAllRequest, $0.AdcReadAllResponse>(
        'AdcReadAll',
        adcReadAll_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.AdcReadAllRequest.fromBuffer(value),
        ($0.AdcReadAllResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.DutPowerEnableRequest,
            $0.DutPowerEnableResponse>(
        'DutPowerEnable',
        dutPowerEnable_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.DutPowerEnableRequest.fromBuffer(value),
        ($0.DutPowerEnableResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.DutPowerEnableRequest,
            $0.DutPowerEnableResponse>(
        'DutChargePowerEnable',
        dutChargePowerEnable_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.DutPowerEnableRequest.fromBuffer(value),
        ($0.DutPowerEnableResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.DutVoltageSetRequest, $0.DutVoltageSetResponse>(
            'DutVoltageSet',
            dutVoltageSet_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.DutVoltageSetRequest.fromBuffer(value),
            ($0.DutVoltageSetResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.DutCurrentReadRequest,
            $0.DutCurrentReadResponse>(
        'DutCurrentRead',
        dutCurrentRead_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.DutCurrentReadRequest.fromBuffer(value),
        ($0.DutCurrentReadResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.DutVoltageReadRequest,
            $0.DutVoltageReadResponse>(
        'DutVoltageRead',
        dutVoltageRead_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.DutVoltageReadRequest.fromBuffer(value),
        ($0.DutVoltageReadResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.DutPowerReadRequest, $0.DutPowerReadResponse>(
            'DutPowerRead',
            dutPowerRead_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.DutPowerReadRequest.fromBuffer(value),
            ($0.DutPowerReadResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.AltimeterReadRequest, $0.AltimeterReadResponse>(
            'AltimeterRead',
            altimeterRead_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.AltimeterReadRequest.fromBuffer(value),
            ($0.AltimeterReadResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.AccelReadRequest, $0.AccelReadResponse>(
        'AccelRead',
        accelRead_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.AccelReadRequest.fromBuffer(value),
        ($0.AccelReadResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.AccelReadMaxRequest, $0.AccelReadMaxResponse>(
            'AccelReadMaxForce',
            accelReadMaxForce_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.AccelReadMaxRequest.fromBuffer(value),
            ($0.AccelReadMaxResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.EepromReadRequest, $0.EepromReadResponse>(
        'EepromRead',
        eepromRead_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.EepromReadRequest.fromBuffer(value),
        ($0.EepromReadResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.EepromWriteRequest, $0.EepromWriteResponse>(
            'EepromWrite',
            eepromWrite_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.EepromWriteRequest.fromBuffer(value),
            ($0.EepromWriteResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.ListFwFilesRequest, $0.ListFwFilesResponse>(
            'ListFwFiles',
            listFwFiles_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.ListFwFilesRequest.fromBuffer(value),
            ($0.ListFwFilesResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.UploadFwFileRequest, $0.UploadFwFileResponse>(
            'UploadFwFile',
            uploadFwFile,
            true,
            false,
            ($core.List<$core.int> value) =>
                $0.UploadFwFileRequest.fromBuffer(value),
            ($0.UploadFwFileResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.DeleteFwFileRequest, $0.DeleteFwFileResponse>(
            'DeleteFwFile',
            deleteFwFile_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.DeleteFwFileRequest.fromBuffer(value),
            ($0.DeleteFwFileResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.FlashHexFileRequest, $0.FlashHexFileResponse>(
            'FlashHexFile',
            flashHexFile_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.FlashHexFileRequest.fromBuffer(value),
            ($0.FlashHexFileResponse value) => value.writeToBuffer()));
  }

  $async.Future<$0.HealthCheckResponse> healthCheck_Pre($grpc.ServiceCall call,
      $async.Future<$0.HealthCheckRequest> request) async {
    return healthCheck(call, await request);
  }

  $async.Future<$0.GpioConfigResponse> gpioConfig_Pre($grpc.ServiceCall call,
      $async.Future<$0.GpioConfigRequest> request) async {
    return gpioConfig(call, await request);
  }

  $async.Future<$0.GpioWriteResponse> gpioWrite_Pre($grpc.ServiceCall call,
      $async.Future<$0.GpioWriteRequest> request) async {
    return gpioWrite(call, await request);
  }

  $async.Future<$0.GpioReadResponse> gpioRead_Pre(
      $grpc.ServiceCall call, $async.Future<$0.GpioReadRequest> request) async {
    return gpioRead(call, await request);
  }

  $async.Future<$0.AdcReadResponse> adcRead_Pre(
      $grpc.ServiceCall call, $async.Future<$0.AdcReadRequest> request) async {
    return adcRead(call, await request);
  }

  $async.Future<$0.AdcReadAllResponse> adcReadAll_Pre($grpc.ServiceCall call,
      $async.Future<$0.AdcReadAllRequest> request) async {
    return adcReadAll(call, await request);
  }

  $async.Future<$0.DutPowerEnableResponse> dutPowerEnable_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutPowerEnableRequest> request) async {
    return dutPowerEnable(call, await request);
  }

  $async.Future<$0.DutPowerEnableResponse> dutChargePowerEnable_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutPowerEnableRequest> request) async {
    return dutChargePowerEnable(call, await request);
  }

  $async.Future<$0.DutVoltageSetResponse> dutVoltageSet_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutVoltageSetRequest> request) async {
    return dutVoltageSet(call, await request);
  }

  $async.Future<$0.DutCurrentReadResponse> dutCurrentRead_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutCurrentReadRequest> request) async {
    return dutCurrentRead(call, await request);
  }

  $async.Future<$0.DutVoltageReadResponse> dutVoltageRead_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutVoltageReadRequest> request) async {
    return dutVoltageRead(call, await request);
  }

  $async.Future<$0.DutPowerReadResponse> dutPowerRead_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutPowerReadRequest> request) async {
    return dutPowerRead(call, await request);
  }

  $async.Future<$0.AltimeterReadResponse> altimeterRead_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.AltimeterReadRequest> request) async {
    return altimeterRead(call, await request);
  }

  $async.Future<$0.AccelReadResponse> accelRead_Pre($grpc.ServiceCall call,
      $async.Future<$0.AccelReadRequest> request) async {
    return accelRead(call, await request);
  }

  $async.Future<$0.AccelReadMaxResponse> accelReadMaxForce_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.AccelReadMaxRequest> request) async {
    return accelReadMaxForce(call, await request);
  }

  $async.Future<$0.EepromReadResponse> eepromRead_Pre($grpc.ServiceCall call,
      $async.Future<$0.EepromReadRequest> request) async {
    return eepromRead(call, await request);
  }

  $async.Future<$0.EepromWriteResponse> eepromWrite_Pre($grpc.ServiceCall call,
      $async.Future<$0.EepromWriteRequest> request) async {
    return eepromWrite(call, await request);
  }

  $async.Future<$0.ListFwFilesResponse> listFwFiles_Pre($grpc.ServiceCall call,
      $async.Future<$0.ListFwFilesRequest> request) async {
    return listFwFiles(call, await request);
  }

  $async.Future<$0.DeleteFwFileResponse> deleteFwFile_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DeleteFwFileRequest> request) async {
    return deleteFwFile(call, await request);
  }

  $async.Future<$0.FlashHexFileResponse> flashHexFile_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.FlashHexFileRequest> request) async {
    return flashHexFile(call, await request);
  }

  $async.Future<$0.HealthCheckResponse> healthCheck(
      $grpc.ServiceCall call, $0.HealthCheckRequest request);
  $async.Future<$0.GpioConfigResponse> gpioConfig(
      $grpc.ServiceCall call, $0.GpioConfigRequest request);
  $async.Future<$0.GpioWriteResponse> gpioWrite(
      $grpc.ServiceCall call, $0.GpioWriteRequest request);
  $async.Future<$0.GpioReadResponse> gpioRead(
      $grpc.ServiceCall call, $0.GpioReadRequest request);
  $async.Future<$0.AdcReadResponse> adcRead(
      $grpc.ServiceCall call, $0.AdcReadRequest request);
  $async.Future<$0.AdcReadAllResponse> adcReadAll(
      $grpc.ServiceCall call, $0.AdcReadAllRequest request);
  $async.Future<$0.DutPowerEnableResponse> dutPowerEnable(
      $grpc.ServiceCall call, $0.DutPowerEnableRequest request);
  $async.Future<$0.DutPowerEnableResponse> dutChargePowerEnable(
      $grpc.ServiceCall call, $0.DutPowerEnableRequest request);
  $async.Future<$0.DutVoltageSetResponse> dutVoltageSet(
      $grpc.ServiceCall call, $0.DutVoltageSetRequest request);
  $async.Future<$0.DutCurrentReadResponse> dutCurrentRead(
      $grpc.ServiceCall call, $0.DutCurrentReadRequest request);
  $async.Future<$0.DutVoltageReadResponse> dutVoltageRead(
      $grpc.ServiceCall call, $0.DutVoltageReadRequest request);
  $async.Future<$0.DutPowerReadResponse> dutPowerRead(
      $grpc.ServiceCall call, $0.DutPowerReadRequest request);
  $async.Future<$0.AltimeterReadResponse> altimeterRead(
      $grpc.ServiceCall call, $0.AltimeterReadRequest request);
  $async.Future<$0.AccelReadResponse> accelRead(
      $grpc.ServiceCall call, $0.AccelReadRequest request);
  $async.Future<$0.AccelReadMaxResponse> accelReadMaxForce(
      $grpc.ServiceCall call, $0.AccelReadMaxRequest request);
  $async.Future<$0.EepromReadResponse> eepromRead(
      $grpc.ServiceCall call, $0.EepromReadRequest request);
  $async.Future<$0.EepromWriteResponse> eepromWrite(
      $grpc.ServiceCall call, $0.EepromWriteRequest request);
  $async.Future<$0.ListFwFilesResponse> listFwFiles(
      $grpc.ServiceCall call, $0.ListFwFilesRequest request);
  $async.Future<$0.UploadFwFileResponse> uploadFwFile(
      $grpc.ServiceCall call, $async.Stream<$0.UploadFwFileRequest> request);
  $async.Future<$0.DeleteFwFileResponse> deleteFwFile(
      $grpc.ServiceCall call, $0.DeleteFwFileRequest request);
  $async.Future<$0.FlashHexFileResponse> flashHexFile(
      $grpc.ServiceCall call, $0.FlashHexFileRequest request);
}

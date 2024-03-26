///
//  Generated code. Do not modify.
//  source: mtib-pi-stm.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:async' as $async;

import 'dart:core' as $core;

import 'package:grpc/service_api.dart' as $grpc;
import 'mtib-pi-stm.pb.dart' as $0;
export 'mtib-pi-stm.pb.dart';

class MtibPiStmClient extends $grpc.Client {
  static final _$gpioConfigurePin = $grpc.ClientMethod<
          $0.GpioConfigurePinRequest, $0.GpioConfigurePinResponse>(
      '/MtibPiStm/GpioConfigurePin',
      ($0.GpioConfigurePinRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.GpioConfigurePinResponse.fromBuffer(value));
  static final _$gpioSetPin =
      $grpc.ClientMethod<$0.GpioSetPinRequest, $0.GpioSetPinResponse>(
          '/MtibPiStm/GpioSetPin',
          ($0.GpioSetPinRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.GpioSetPinResponse.fromBuffer(value));
  static final _$gpioReadPin =
      $grpc.ClientMethod<$0.GpioReadPinRequest, $0.GpioReadPinResponse>(
          '/MtibPiStm/GpioReadPin',
          ($0.GpioReadPinRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.GpioReadPinResponse.fromBuffer(value));
  static final _$adcReadChannel =
      $grpc.ClientMethod<$0.AdcReadChannelRequest, $0.AdcReadChannelResponse>(
          '/MtibPiStm/AdcReadChannel',
          ($0.AdcReadChannelRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.AdcReadChannelResponse.fromBuffer(value));
  static final _$adcReadAllChannels = $grpc.ClientMethod<
          $0.AdcReadAllChannelsRequest, $0.AdcReadAllChannelsResponse>(
      '/MtibPiStm/AdcReadAllChannels',
      ($0.AdcReadAllChannelsRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.AdcReadAllChannelsResponse.fromBuffer(value));
  static final _$dutEnablePower =
      $grpc.ClientMethod<$0.DutEnablePowerRequest, $0.DutEnablePowerResponse>(
          '/MtibPiStm/DutEnablePower',
          ($0.DutEnablePowerRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.DutEnablePowerResponse.fromBuffer(value));
  static final _$dutEnableCharger = $grpc.ClientMethod<
          $0.DutEnableChargerRequest, $0.DutEnableChargerResponse>(
      '/MtibPiStm/DutEnableCharger',
      ($0.DutEnableChargerRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.DutEnableChargerResponse.fromBuffer(value));
  static final _$dutSetOutputVoltage = $grpc.ClientMethod<
          $0.DutSetOutputVoltageRequest, $0.DutSetOutputVoltageResponse>(
      '/MtibPiStm/DutSetOutputVoltage',
      ($0.DutSetOutputVoltageRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.DutSetOutputVoltageResponse.fromBuffer(value));
  static final _$ina219ReadCurrent = $grpc.ClientMethod<
          $0.Ina219ReadCurrentRequest, $0.Ina219ReadCurrentResponse>(
      '/MtibPiStm/Ina219ReadCurrent',
      ($0.Ina219ReadCurrentRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.Ina219ReadCurrentResponse.fromBuffer(value));
  static final _$ina219ReadVoltage = $grpc.ClientMethod<
          $0.Ina219ReadVoltageRequest, $0.Ina219ReadVoltageResponse>(
      '/MtibPiStm/Ina219ReadVoltage',
      ($0.Ina219ReadVoltageRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.Ina219ReadVoltageResponse.fromBuffer(value));
  static final _$ina219ReadPower =
      $grpc.ClientMethod<$0.Ina219ReadPowerRequest, $0.Ina219ReadPowerResponse>(
          '/MtibPiStm/Ina219ReadPower',
          ($0.Ina219ReadPowerRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.Ina219ReadPowerResponse.fromBuffer(value));
  static final _$bmp390ReadValues = $grpc.ClientMethod<
          $0.Bmp390ReadValuesRequest, $0.Bmp390ReadValuesResponse>(
      '/MtibPiStm/Bmp390ReadValues',
      ($0.Bmp390ReadValuesRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.Bmp390ReadValuesResponse.fromBuffer(value));
  static final _$lis2de12ReadValues = $grpc.ClientMethod<
          $0.Lis2de12ReadValuesRequest, $0.Lis2de12ReadValuesResponse>(
      '/MtibPiStm/Lis2de12ReadValues',
      ($0.Lis2de12ReadValuesRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.Lis2de12ReadValuesResponse.fromBuffer(value));
  static final _$lis2de12ReadMaxForce = $grpc.ClientMethod<
          $0.Lis2de12ReadMaxForceRequest, $0.Lis2de12ReadMaxForceResponse>(
      '/MtibPiStm/Lis2de12ReadMaxForce',
      ($0.Lis2de12ReadMaxForceRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.Lis2de12ReadMaxForceResponse.fromBuffer(value));
  static final _$eepromReadFromMem = $grpc.ClientMethod<
          $0.EepromReadFromMemRequest, $0.EepromReadFromMemResponse>(
      '/MtibPiStm/EepromReadFromMem',
      ($0.EepromReadFromMemRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.EepromReadFromMemResponse.fromBuffer(value));
  static final _$eepromWriteToMem = $grpc.ClientMethod<
          $0.EepromWriteToMemRequest, $0.EepromWriteToMemResponse>(
      '/MtibPiStm/EepromWriteToMem',
      ($0.EepromWriteToMemRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) =>
          $0.EepromWriteToMemResponse.fromBuffer(value));
  static final _$sigmaToPiMessage =
      $grpc.ClientMethod<$0.UartMessageRequest, $0.UartMessageResponse>(
          '/MtibPiStm/SigmaToPiMessage',
          ($0.UartMessageRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.UartMessageResponse.fromBuffer(value));
  static final _$piToSigmaMessage =
      $grpc.ClientMethod<$0.UartMessageRequest, $0.UartMessageResponse>(
          '/MtibPiStm/PiToSigmaMessage',
          ($0.UartMessageRequest value) => value.writeToBuffer(),
          ($core.List<$core.int> value) =>
              $0.UartMessageResponse.fromBuffer(value));

  MtibPiStmClient($grpc.ClientChannel channel,
      {$grpc.CallOptions? options,
      $core.Iterable<$grpc.ClientInterceptor>? interceptors})
      : super(channel, options: options, interceptors: interceptors);

  $grpc.ResponseFuture<$0.GpioConfigurePinResponse> gpioConfigurePin(
      $0.GpioConfigurePinRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$gpioConfigurePin, request, options: options);
  }

  $grpc.ResponseFuture<$0.GpioSetPinResponse> gpioSetPin(
      $0.GpioSetPinRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$gpioSetPin, request, options: options);
  }

  $grpc.ResponseFuture<$0.GpioReadPinResponse> gpioReadPin(
      $0.GpioReadPinRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$gpioReadPin, request, options: options);
  }

  $grpc.ResponseFuture<$0.AdcReadChannelResponse> adcReadChannel(
      $0.AdcReadChannelRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$adcReadChannel, request, options: options);
  }

  $grpc.ResponseFuture<$0.AdcReadAllChannelsResponse> adcReadAllChannels(
      $0.AdcReadAllChannelsRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$adcReadAllChannels, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutEnablePowerResponse> dutEnablePower(
      $0.DutEnablePowerRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutEnablePower, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutEnableChargerResponse> dutEnableCharger(
      $0.DutEnableChargerRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutEnableCharger, request, options: options);
  }

  $grpc.ResponseFuture<$0.DutSetOutputVoltageResponse> dutSetOutputVoltage(
      $0.DutSetOutputVoltageRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$dutSetOutputVoltage, request, options: options);
  }

  $grpc.ResponseFuture<$0.Ina219ReadCurrentResponse> ina219ReadCurrent(
      $0.Ina219ReadCurrentRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$ina219ReadCurrent, request, options: options);
  }

  $grpc.ResponseFuture<$0.Ina219ReadVoltageResponse> ina219ReadVoltage(
      $0.Ina219ReadVoltageRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$ina219ReadVoltage, request, options: options);
  }

  $grpc.ResponseFuture<$0.Ina219ReadPowerResponse> ina219ReadPower(
      $0.Ina219ReadPowerRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$ina219ReadPower, request, options: options);
  }

  $grpc.ResponseFuture<$0.Bmp390ReadValuesResponse> bmp390ReadValues(
      $0.Bmp390ReadValuesRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$bmp390ReadValues, request, options: options);
  }

  $grpc.ResponseFuture<$0.Lis2de12ReadValuesResponse> lis2de12ReadValues(
      $0.Lis2de12ReadValuesRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$lis2de12ReadValues, request, options: options);
  }

  $grpc.ResponseFuture<$0.Lis2de12ReadMaxForceResponse> lis2de12ReadMaxForce(
      $0.Lis2de12ReadMaxForceRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$lis2de12ReadMaxForce, request, options: options);
  }

  $grpc.ResponseFuture<$0.EepromReadFromMemResponse> eepromReadFromMem(
      $0.EepromReadFromMemRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$eepromReadFromMem, request, options: options);
  }

  $grpc.ResponseFuture<$0.EepromWriteToMemResponse> eepromWriteToMem(
      $0.EepromWriteToMemRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$eepromWriteToMem, request, options: options);
  }

  $grpc.ResponseFuture<$0.UartMessageResponse> sigmaToPiMessage(
      $0.UartMessageRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$sigmaToPiMessage, request, options: options);
  }

  $grpc.ResponseFuture<$0.UartMessageResponse> piToSigmaMessage(
      $0.UartMessageRequest request,
      {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$piToSigmaMessage, request, options: options);
  }
}

abstract class MtibPiStmServiceBase extends $grpc.Service {
  $core.String get $name => 'MtibPiStm';

  MtibPiStmServiceBase() {
    $addMethod($grpc.ServiceMethod<$0.GpioConfigurePinRequest,
            $0.GpioConfigurePinResponse>(
        'GpioConfigurePin',
        gpioConfigurePin_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.GpioConfigurePinRequest.fromBuffer(value),
        ($0.GpioConfigurePinResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.GpioSetPinRequest, $0.GpioSetPinResponse>(
        'GpioSetPin',
        gpioSetPin_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.GpioSetPinRequest.fromBuffer(value),
        ($0.GpioSetPinResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.GpioReadPinRequest, $0.GpioReadPinResponse>(
            'GpioReadPin',
            gpioReadPin_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.GpioReadPinRequest.fromBuffer(value),
            ($0.GpioReadPinResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.AdcReadChannelRequest,
            $0.AdcReadChannelResponse>(
        'AdcReadChannel',
        adcReadChannel_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.AdcReadChannelRequest.fromBuffer(value),
        ($0.AdcReadChannelResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.AdcReadAllChannelsRequest,
            $0.AdcReadAllChannelsResponse>(
        'AdcReadAllChannels',
        adcReadAllChannels_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.AdcReadAllChannelsRequest.fromBuffer(value),
        ($0.AdcReadAllChannelsResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.DutEnablePowerRequest,
            $0.DutEnablePowerResponse>(
        'DutEnablePower',
        dutEnablePower_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.DutEnablePowerRequest.fromBuffer(value),
        ($0.DutEnablePowerResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.DutEnableChargerRequest,
            $0.DutEnableChargerResponse>(
        'DutEnableCharger',
        dutEnableCharger_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.DutEnableChargerRequest.fromBuffer(value),
        ($0.DutEnableChargerResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.DutSetOutputVoltageRequest,
            $0.DutSetOutputVoltageResponse>(
        'DutSetOutputVoltage',
        dutSetOutputVoltage_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.DutSetOutputVoltageRequest.fromBuffer(value),
        ($0.DutSetOutputVoltageResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Ina219ReadCurrentRequest,
            $0.Ina219ReadCurrentResponse>(
        'Ina219ReadCurrent',
        ina219ReadCurrent_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.Ina219ReadCurrentRequest.fromBuffer(value),
        ($0.Ina219ReadCurrentResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Ina219ReadVoltageRequest,
            $0.Ina219ReadVoltageResponse>(
        'Ina219ReadVoltage',
        ina219ReadVoltage_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.Ina219ReadVoltageRequest.fromBuffer(value),
        ($0.Ina219ReadVoltageResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Ina219ReadPowerRequest,
            $0.Ina219ReadPowerResponse>(
        'Ina219ReadPower',
        ina219ReadPower_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.Ina219ReadPowerRequest.fromBuffer(value),
        ($0.Ina219ReadPowerResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Bmp390ReadValuesRequest,
            $0.Bmp390ReadValuesResponse>(
        'Bmp390ReadValues',
        bmp390ReadValues_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.Bmp390ReadValuesRequest.fromBuffer(value),
        ($0.Bmp390ReadValuesResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Lis2de12ReadValuesRequest,
            $0.Lis2de12ReadValuesResponse>(
        'Lis2de12ReadValues',
        lis2de12ReadValues_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.Lis2de12ReadValuesRequest.fromBuffer(value),
        ($0.Lis2de12ReadValuesResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Lis2de12ReadMaxForceRequest,
            $0.Lis2de12ReadMaxForceResponse>(
        'Lis2de12ReadMaxForce',
        lis2de12ReadMaxForce_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.Lis2de12ReadMaxForceRequest.fromBuffer(value),
        ($0.Lis2de12ReadMaxForceResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.EepromReadFromMemRequest,
            $0.EepromReadFromMemResponse>(
        'EepromReadFromMem',
        eepromReadFromMem_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.EepromReadFromMemRequest.fromBuffer(value),
        ($0.EepromReadFromMemResponse value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.EepromWriteToMemRequest,
            $0.EepromWriteToMemResponse>(
        'EepromWriteToMem',
        eepromWriteToMem_Pre,
        false,
        false,
        ($core.List<$core.int> value) =>
            $0.EepromWriteToMemRequest.fromBuffer(value),
        ($0.EepromWriteToMemResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.UartMessageRequest, $0.UartMessageResponse>(
            'SigmaToPiMessage',
            sigmaToPiMessage_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.UartMessageRequest.fromBuffer(value),
            ($0.UartMessageResponse value) => value.writeToBuffer()));
    $addMethod(
        $grpc.ServiceMethod<$0.UartMessageRequest, $0.UartMessageResponse>(
            'PiToSigmaMessage',
            piToSigmaMessage_Pre,
            false,
            false,
            ($core.List<$core.int> value) =>
                $0.UartMessageRequest.fromBuffer(value),
            ($0.UartMessageResponse value) => value.writeToBuffer()));
  }

  $async.Future<$0.GpioConfigurePinResponse> gpioConfigurePin_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.GpioConfigurePinRequest> request) async {
    return gpioConfigurePin(call, await request);
  }

  $async.Future<$0.GpioSetPinResponse> gpioSetPin_Pre($grpc.ServiceCall call,
      $async.Future<$0.GpioSetPinRequest> request) async {
    return gpioSetPin(call, await request);
  }

  $async.Future<$0.GpioReadPinResponse> gpioReadPin_Pre($grpc.ServiceCall call,
      $async.Future<$0.GpioReadPinRequest> request) async {
    return gpioReadPin(call, await request);
  }

  $async.Future<$0.AdcReadChannelResponse> adcReadChannel_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.AdcReadChannelRequest> request) async {
    return adcReadChannel(call, await request);
  }

  $async.Future<$0.AdcReadAllChannelsResponse> adcReadAllChannels_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.AdcReadAllChannelsRequest> request) async {
    return adcReadAllChannels(call, await request);
  }

  $async.Future<$0.DutEnablePowerResponse> dutEnablePower_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutEnablePowerRequest> request) async {
    return dutEnablePower(call, await request);
  }

  $async.Future<$0.DutEnableChargerResponse> dutEnableCharger_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutEnableChargerRequest> request) async {
    return dutEnableCharger(call, await request);
  }

  $async.Future<$0.DutSetOutputVoltageResponse> dutSetOutputVoltage_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.DutSetOutputVoltageRequest> request) async {
    return dutSetOutputVoltage(call, await request);
  }

  $async.Future<$0.Ina219ReadCurrentResponse> ina219ReadCurrent_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.Ina219ReadCurrentRequest> request) async {
    return ina219ReadCurrent(call, await request);
  }

  $async.Future<$0.Ina219ReadVoltageResponse> ina219ReadVoltage_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.Ina219ReadVoltageRequest> request) async {
    return ina219ReadVoltage(call, await request);
  }

  $async.Future<$0.Ina219ReadPowerResponse> ina219ReadPower_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.Ina219ReadPowerRequest> request) async {
    return ina219ReadPower(call, await request);
  }

  $async.Future<$0.Bmp390ReadValuesResponse> bmp390ReadValues_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.Bmp390ReadValuesRequest> request) async {
    return bmp390ReadValues(call, await request);
  }

  $async.Future<$0.Lis2de12ReadValuesResponse> lis2de12ReadValues_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.Lis2de12ReadValuesRequest> request) async {
    return lis2de12ReadValues(call, await request);
  }

  $async.Future<$0.Lis2de12ReadMaxForceResponse> lis2de12ReadMaxForce_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.Lis2de12ReadMaxForceRequest> request) async {
    return lis2de12ReadMaxForce(call, await request);
  }

  $async.Future<$0.EepromReadFromMemResponse> eepromReadFromMem_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.EepromReadFromMemRequest> request) async {
    return eepromReadFromMem(call, await request);
  }

  $async.Future<$0.EepromWriteToMemResponse> eepromWriteToMem_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.EepromWriteToMemRequest> request) async {
    return eepromWriteToMem(call, await request);
  }

  $async.Future<$0.UartMessageResponse> sigmaToPiMessage_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.UartMessageRequest> request) async {
    return sigmaToPiMessage(call, await request);
  }

  $async.Future<$0.UartMessageResponse> piToSigmaMessage_Pre(
      $grpc.ServiceCall call,
      $async.Future<$0.UartMessageRequest> request) async {
    return piToSigmaMessage(call, await request);
  }

  $async.Future<$0.GpioConfigurePinResponse> gpioConfigurePin(
      $grpc.ServiceCall call, $0.GpioConfigurePinRequest request);
  $async.Future<$0.GpioSetPinResponse> gpioSetPin(
      $grpc.ServiceCall call, $0.GpioSetPinRequest request);
  $async.Future<$0.GpioReadPinResponse> gpioReadPin(
      $grpc.ServiceCall call, $0.GpioReadPinRequest request);
  $async.Future<$0.AdcReadChannelResponse> adcReadChannel(
      $grpc.ServiceCall call, $0.AdcReadChannelRequest request);
  $async.Future<$0.AdcReadAllChannelsResponse> adcReadAllChannels(
      $grpc.ServiceCall call, $0.AdcReadAllChannelsRequest request);
  $async.Future<$0.DutEnablePowerResponse> dutEnablePower(
      $grpc.ServiceCall call, $0.DutEnablePowerRequest request);
  $async.Future<$0.DutEnableChargerResponse> dutEnableCharger(
      $grpc.ServiceCall call, $0.DutEnableChargerRequest request);
  $async.Future<$0.DutSetOutputVoltageResponse> dutSetOutputVoltage(
      $grpc.ServiceCall call, $0.DutSetOutputVoltageRequest request);
  $async.Future<$0.Ina219ReadCurrentResponse> ina219ReadCurrent(
      $grpc.ServiceCall call, $0.Ina219ReadCurrentRequest request);
  $async.Future<$0.Ina219ReadVoltageResponse> ina219ReadVoltage(
      $grpc.ServiceCall call, $0.Ina219ReadVoltageRequest request);
  $async.Future<$0.Ina219ReadPowerResponse> ina219ReadPower(
      $grpc.ServiceCall call, $0.Ina219ReadPowerRequest request);
  $async.Future<$0.Bmp390ReadValuesResponse> bmp390ReadValues(
      $grpc.ServiceCall call, $0.Bmp390ReadValuesRequest request);
  $async.Future<$0.Lis2de12ReadValuesResponse> lis2de12ReadValues(
      $grpc.ServiceCall call, $0.Lis2de12ReadValuesRequest request);
  $async.Future<$0.Lis2de12ReadMaxForceResponse> lis2de12ReadMaxForce(
      $grpc.ServiceCall call, $0.Lis2de12ReadMaxForceRequest request);
  $async.Future<$0.EepromReadFromMemResponse> eepromReadFromMem(
      $grpc.ServiceCall call, $0.EepromReadFromMemRequest request);
  $async.Future<$0.EepromWriteToMemResponse> eepromWriteToMem(
      $grpc.ServiceCall call, $0.EepromWriteToMemRequest request);
  $async.Future<$0.UartMessageResponse> sigmaToPiMessage(
      $grpc.ServiceCall call, $0.UartMessageRequest request);
  $async.Future<$0.UartMessageResponse> piToSigmaMessage(
      $grpc.ServiceCall call, $0.UartMessageRequest request);
}

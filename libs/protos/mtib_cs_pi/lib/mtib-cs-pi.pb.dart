///
//  Generated code. Do not modify.
//  source: mtib-cs-pi.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:core' as $core;

import 'package:fixnum/fixnum.dart' as $fixnum;
import 'package:protobuf/protobuf.dart' as $pb;

import 'mtib-cs-pi.pbenum.dart';

export 'mtib-cs-pi.pbenum.dart';

class HealthCheckRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'HealthCheckRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  HealthCheckRequest._() : super();
  factory HealthCheckRequest() => create();
  factory HealthCheckRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory HealthCheckRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  HealthCheckRequest clone() => HealthCheckRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  HealthCheckRequest copyWith(void Function(HealthCheckRequest) updates) => super.copyWith((message) => updates(message as HealthCheckRequest)) as HealthCheckRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static HealthCheckRequest create() => HealthCheckRequest._();
  HealthCheckRequest createEmptyInstance() => create();
  static $pb.PbList<HealthCheckRequest> createRepeated() => $pb.PbList<HealthCheckRequest>();
  @$core.pragma('dart2js:noInline')
  static HealthCheckRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<HealthCheckRequest>(create);
  static HealthCheckRequest? _defaultInstance;
}

class HealthCheckResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'HealthCheckResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'ok')
    ..hasRequiredFields = false
  ;

  HealthCheckResponse._() : super();
  factory HealthCheckResponse({
    $core.bool? ok,
  }) {
    final _result = create();
    if (ok != null) {
      _result.ok = ok;
    }
    return _result;
  }
  factory HealthCheckResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory HealthCheckResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  HealthCheckResponse clone() => HealthCheckResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  HealthCheckResponse copyWith(void Function(HealthCheckResponse) updates) => super.copyWith((message) => updates(message as HealthCheckResponse)) as HealthCheckResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static HealthCheckResponse create() => HealthCheckResponse._();
  HealthCheckResponse createEmptyInstance() => create();
  static $pb.PbList<HealthCheckResponse> createRepeated() => $pb.PbList<HealthCheckResponse>();
  @$core.pragma('dart2js:noInline')
  static HealthCheckResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<HealthCheckResponse>(create);
  static HealthCheckResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get ok => $_getBF(0);
  @$pb.TagNumber(1)
  set ok($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasOk() => $_has(0);
  @$pb.TagNumber(1)
  void clearOk() => clearField(1);
}

class GpioConfigRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioConfigRequest', createEmptyInstance: create)
    ..e<Gpio>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'gpio', $pb.PbFieldType.OE, defaultOrMaker: Gpio.GPIO_0, valueOf: Gpio.valueOf, enumValues: Gpio.values)
    ..e<GpioType>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'type', $pb.PbFieldType.OE, defaultOrMaker: GpioType.GPIO_INPUT, valueOf: GpioType.valueOf, enumValues: GpioType.values)
    ..e<GpioResistorConfig>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'resistor', $pb.PbFieldType.OE, defaultOrMaker: GpioResistorConfig.GPIO_RESISTOR_PULL_UP, valueOf: GpioResistorConfig.valueOf, enumValues: GpioResistorConfig.values)
    ..hasRequiredFields = false
  ;

  GpioConfigRequest._() : super();
  factory GpioConfigRequest({
    Gpio? gpio,
    GpioType? type,
    GpioResistorConfig? resistor,
  }) {
    final _result = create();
    if (gpio != null) {
      _result.gpio = gpio;
    }
    if (type != null) {
      _result.type = type;
    }
    if (resistor != null) {
      _result.resistor = resistor;
    }
    return _result;
  }
  factory GpioConfigRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioConfigRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioConfigRequest clone() => GpioConfigRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioConfigRequest copyWith(void Function(GpioConfigRequest) updates) => super.copyWith((message) => updates(message as GpioConfigRequest)) as GpioConfigRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioConfigRequest create() => GpioConfigRequest._();
  GpioConfigRequest createEmptyInstance() => create();
  static $pb.PbList<GpioConfigRequest> createRepeated() => $pb.PbList<GpioConfigRequest>();
  @$core.pragma('dart2js:noInline')
  static GpioConfigRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioConfigRequest>(create);
  static GpioConfigRequest? _defaultInstance;

  @$pb.TagNumber(1)
  Gpio get gpio => $_getN(0);
  @$pb.TagNumber(1)
  set gpio(Gpio v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasGpio() => $_has(0);
  @$pb.TagNumber(1)
  void clearGpio() => clearField(1);

  @$pb.TagNumber(2)
  GpioType get type => $_getN(1);
  @$pb.TagNumber(2)
  set type(GpioType v) { setField(2, v); }
  @$pb.TagNumber(2)
  $core.bool hasType() => $_has(1);
  @$pb.TagNumber(2)
  void clearType() => clearField(2);

  @$pb.TagNumber(3)
  GpioResistorConfig get resistor => $_getN(2);
  @$pb.TagNumber(3)
  set resistor(GpioResistorConfig v) { setField(3, v); }
  @$pb.TagNumber(3)
  $core.bool hasResistor() => $_has(2);
  @$pb.TagNumber(3)
  void clearResistor() => clearField(3);
}

class GpioConfigResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioConfigResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  GpioConfigResponse._() : super();
  factory GpioConfigResponse({
    $core.bool? success,
    $core.String? error,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    return _result;
  }
  factory GpioConfigResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioConfigResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioConfigResponse clone() => GpioConfigResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioConfigResponse copyWith(void Function(GpioConfigResponse) updates) => super.copyWith((message) => updates(message as GpioConfigResponse)) as GpioConfigResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioConfigResponse create() => GpioConfigResponse._();
  GpioConfigResponse createEmptyInstance() => create();
  static $pb.PbList<GpioConfigResponse> createRepeated() => $pb.PbList<GpioConfigResponse>();
  @$core.pragma('dart2js:noInline')
  static GpioConfigResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioConfigResponse>(create);
  static GpioConfigResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);
}

class GpioWriteRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioWriteRequest', createEmptyInstance: create)
    ..e<Gpio>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'gpio', $pb.PbFieldType.OE, defaultOrMaker: Gpio.GPIO_0, valueOf: Gpio.valueOf, enumValues: Gpio.values)
    ..aOB(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'state')
    ..hasRequiredFields = false
  ;

  GpioWriteRequest._() : super();
  factory GpioWriteRequest({
    Gpio? gpio,
    $core.bool? state,
  }) {
    final _result = create();
    if (gpio != null) {
      _result.gpio = gpio;
    }
    if (state != null) {
      _result.state = state;
    }
    return _result;
  }
  factory GpioWriteRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioWriteRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioWriteRequest clone() => GpioWriteRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioWriteRequest copyWith(void Function(GpioWriteRequest) updates) => super.copyWith((message) => updates(message as GpioWriteRequest)) as GpioWriteRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioWriteRequest create() => GpioWriteRequest._();
  GpioWriteRequest createEmptyInstance() => create();
  static $pb.PbList<GpioWriteRequest> createRepeated() => $pb.PbList<GpioWriteRequest>();
  @$core.pragma('dart2js:noInline')
  static GpioWriteRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioWriteRequest>(create);
  static GpioWriteRequest? _defaultInstance;

  @$pb.TagNumber(1)
  Gpio get gpio => $_getN(0);
  @$pb.TagNumber(1)
  set gpio(Gpio v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasGpio() => $_has(0);
  @$pb.TagNumber(1)
  void clearGpio() => clearField(1);

  @$pb.TagNumber(2)
  $core.bool get state => $_getBF(1);
  @$pb.TagNumber(2)
  set state($core.bool v) { $_setBool(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasState() => $_has(1);
  @$pb.TagNumber(2)
  void clearState() => clearField(2);
}

class GpioWriteResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioWriteResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  GpioWriteResponse._() : super();
  factory GpioWriteResponse({
    $core.bool? success,
    $core.String? error,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    return _result;
  }
  factory GpioWriteResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioWriteResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioWriteResponse clone() => GpioWriteResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioWriteResponse copyWith(void Function(GpioWriteResponse) updates) => super.copyWith((message) => updates(message as GpioWriteResponse)) as GpioWriteResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioWriteResponse create() => GpioWriteResponse._();
  GpioWriteResponse createEmptyInstance() => create();
  static $pb.PbList<GpioWriteResponse> createRepeated() => $pb.PbList<GpioWriteResponse>();
  @$core.pragma('dart2js:noInline')
  static GpioWriteResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioWriteResponse>(create);
  static GpioWriteResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);
}

class GpioReadRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioReadRequest', createEmptyInstance: create)
    ..e<Gpio>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'gpio', $pb.PbFieldType.OE, defaultOrMaker: Gpio.GPIO_0, valueOf: Gpio.valueOf, enumValues: Gpio.values)
    ..hasRequiredFields = false
  ;

  GpioReadRequest._() : super();
  factory GpioReadRequest({
    Gpio? gpio,
  }) {
    final _result = create();
    if (gpio != null) {
      _result.gpio = gpio;
    }
    return _result;
  }
  factory GpioReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioReadRequest clone() => GpioReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioReadRequest copyWith(void Function(GpioReadRequest) updates) => super.copyWith((message) => updates(message as GpioReadRequest)) as GpioReadRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioReadRequest create() => GpioReadRequest._();
  GpioReadRequest createEmptyInstance() => create();
  static $pb.PbList<GpioReadRequest> createRepeated() => $pb.PbList<GpioReadRequest>();
  @$core.pragma('dart2js:noInline')
  static GpioReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioReadRequest>(create);
  static GpioReadRequest? _defaultInstance;

  @$pb.TagNumber(1)
  Gpio get gpio => $_getN(0);
  @$pb.TagNumber(1)
  set gpio(Gpio v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasGpio() => $_has(0);
  @$pb.TagNumber(1)
  void clearGpio() => clearField(1);
}

class GpioReadResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioReadResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..aOB(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'state')
    ..hasRequiredFields = false
  ;

  GpioReadResponse._() : super();
  factory GpioReadResponse({
    $core.bool? success,
    $core.String? error,
    $core.bool? state,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (state != null) {
      _result.state = state;
    }
    return _result;
  }
  factory GpioReadResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioReadResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioReadResponse clone() => GpioReadResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioReadResponse copyWith(void Function(GpioReadResponse) updates) => super.copyWith((message) => updates(message as GpioReadResponse)) as GpioReadResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioReadResponse create() => GpioReadResponse._();
  GpioReadResponse createEmptyInstance() => create();
  static $pb.PbList<GpioReadResponse> createRepeated() => $pb.PbList<GpioReadResponse>();
  @$core.pragma('dart2js:noInline')
  static GpioReadResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioReadResponse>(create);
  static GpioReadResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.bool get state => $_getBF(2);
  @$pb.TagNumber(3)
  set state($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasState() => $_has(2);
  @$pb.TagNumber(3)
  void clearState() => clearField(3);
}

class AdcReadRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdcReadRequest', createEmptyInstance: create)
    ..e<AdcChannel>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'channel', $pb.PbFieldType.OE, defaultOrMaker: AdcChannel.ADC_CHANNEL_0, valueOf: AdcChannel.valueOf, enumValues: AdcChannel.values)
    ..a<$core.int>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'delayMs', $pb.PbFieldType.O3, protoName: 'delayMs')
    ..hasRequiredFields = false
  ;

  AdcReadRequest._() : super();
  factory AdcReadRequest({
    AdcChannel? channel,
    $core.int? delayMs,
  }) {
    final _result = create();
    if (channel != null) {
      _result.channel = channel;
    }
    if (delayMs != null) {
      _result.delayMs = delayMs;
    }
    return _result;
  }
  factory AdcReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdcReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdcReadRequest clone() => AdcReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdcReadRequest copyWith(void Function(AdcReadRequest) updates) => super.copyWith((message) => updates(message as AdcReadRequest)) as AdcReadRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdcReadRequest create() => AdcReadRequest._();
  AdcReadRequest createEmptyInstance() => create();
  static $pb.PbList<AdcReadRequest> createRepeated() => $pb.PbList<AdcReadRequest>();
  @$core.pragma('dart2js:noInline')
  static AdcReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdcReadRequest>(create);
  static AdcReadRequest? _defaultInstance;

  @$pb.TagNumber(1)
  AdcChannel get channel => $_getN(0);
  @$pb.TagNumber(1)
  set channel(AdcChannel v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasChannel() => $_has(0);
  @$pb.TagNumber(1)
  void clearChannel() => clearField(1);

  @$pb.TagNumber(2)
  $core.int get delayMs => $_getIZ(1);
  @$pb.TagNumber(2)
  set delayMs($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDelayMs() => $_has(1);
  @$pb.TagNumber(2)
  void clearDelayMs() => clearField(2);
}

class AdcReadResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdcReadResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voltage', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  AdcReadResponse._() : super();
  factory AdcReadResponse({
    $core.bool? success,
    $core.String? error,
    $core.double? voltage,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (voltage != null) {
      _result.voltage = voltage;
    }
    return _result;
  }
  factory AdcReadResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdcReadResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdcReadResponse clone() => AdcReadResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdcReadResponse copyWith(void Function(AdcReadResponse) updates) => super.copyWith((message) => updates(message as AdcReadResponse)) as AdcReadResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdcReadResponse create() => AdcReadResponse._();
  AdcReadResponse createEmptyInstance() => create();
  static $pb.PbList<AdcReadResponse> createRepeated() => $pb.PbList<AdcReadResponse>();
  @$core.pragma('dart2js:noInline')
  static AdcReadResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdcReadResponse>(create);
  static AdcReadResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get voltage => $_getN(2);
  @$pb.TagNumber(3)
  set voltage($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasVoltage() => $_has(2);
  @$pb.TagNumber(3)
  void clearVoltage() => clearField(3);
}

class AdcReadAllRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdcReadAllRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'delayMs', $pb.PbFieldType.O3, protoName: 'delayMs')
    ..hasRequiredFields = false
  ;

  AdcReadAllRequest._() : super();
  factory AdcReadAllRequest({
    $core.int? delayMs,
  }) {
    final _result = create();
    if (delayMs != null) {
      _result.delayMs = delayMs;
    }
    return _result;
  }
  factory AdcReadAllRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdcReadAllRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdcReadAllRequest clone() => AdcReadAllRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdcReadAllRequest copyWith(void Function(AdcReadAllRequest) updates) => super.copyWith((message) => updates(message as AdcReadAllRequest)) as AdcReadAllRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdcReadAllRequest create() => AdcReadAllRequest._();
  AdcReadAllRequest createEmptyInstance() => create();
  static $pb.PbList<AdcReadAllRequest> createRepeated() => $pb.PbList<AdcReadAllRequest>();
  @$core.pragma('dart2js:noInline')
  static AdcReadAllRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdcReadAllRequest>(create);
  static AdcReadAllRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get delayMs => $_getIZ(0);
  @$pb.TagNumber(1)
  set delayMs($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasDelayMs() => $_has(0);
  @$pb.TagNumber(1)
  void clearDelayMs() => clearField(1);
}

class AdcReadAllResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdcReadAllResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..p<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voltage', $pb.PbFieldType.KD)
    ..hasRequiredFields = false
  ;

  AdcReadAllResponse._() : super();
  factory AdcReadAllResponse({
    $core.bool? success,
    $core.String? error,
    $core.Iterable<$core.double>? voltage,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (voltage != null) {
      _result.voltage.addAll(voltage);
    }
    return _result;
  }
  factory AdcReadAllResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdcReadAllResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdcReadAllResponse clone() => AdcReadAllResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdcReadAllResponse copyWith(void Function(AdcReadAllResponse) updates) => super.copyWith((message) => updates(message as AdcReadAllResponse)) as AdcReadAllResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdcReadAllResponse create() => AdcReadAllResponse._();
  AdcReadAllResponse createEmptyInstance() => create();
  static $pb.PbList<AdcReadAllResponse> createRepeated() => $pb.PbList<AdcReadAllResponse>();
  @$core.pragma('dart2js:noInline')
  static AdcReadAllResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdcReadAllResponse>(create);
  static AdcReadAllResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.List<$core.double> get voltage => $_getList(2);
}

class UartConfigRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'UartConfigRequest', createEmptyInstance: create)
    ..e<UartPort>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'port', $pb.PbFieldType.OE, defaultOrMaker: UartPort.UART_PORT_0, valueOf: UartPort.valueOf, enumValues: UartPort.values)
    ..e<UartBaudRate>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'baud', $pb.PbFieldType.OE, defaultOrMaker: UartBaudRate.UART_BAUDRATE_9600, valueOf: UartBaudRate.valueOf, enumValues: UartBaudRate.values)
    ..aOB(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'enable')
    ..hasRequiredFields = false
  ;

  UartConfigRequest._() : super();
  factory UartConfigRequest({
    UartPort? port,
    UartBaudRate? baud,
    $core.bool? enable,
  }) {
    final _result = create();
    if (port != null) {
      _result.port = port;
    }
    if (baud != null) {
      _result.baud = baud;
    }
    if (enable != null) {
      _result.enable = enable;
    }
    return _result;
  }
  factory UartConfigRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory UartConfigRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  UartConfigRequest clone() => UartConfigRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  UartConfigRequest copyWith(void Function(UartConfigRequest) updates) => super.copyWith((message) => updates(message as UartConfigRequest)) as UartConfigRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static UartConfigRequest create() => UartConfigRequest._();
  UartConfigRequest createEmptyInstance() => create();
  static $pb.PbList<UartConfigRequest> createRepeated() => $pb.PbList<UartConfigRequest>();
  @$core.pragma('dart2js:noInline')
  static UartConfigRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<UartConfigRequest>(create);
  static UartConfigRequest? _defaultInstance;

  @$pb.TagNumber(1)
  UartPort get port => $_getN(0);
  @$pb.TagNumber(1)
  set port(UartPort v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasPort() => $_has(0);
  @$pb.TagNumber(1)
  void clearPort() => clearField(1);

  @$pb.TagNumber(2)
  UartBaudRate get baud => $_getN(1);
  @$pb.TagNumber(2)
  set baud(UartBaudRate v) { setField(2, v); }
  @$pb.TagNumber(2)
  $core.bool hasBaud() => $_has(1);
  @$pb.TagNumber(2)
  void clearBaud() => clearField(2);

  @$pb.TagNumber(3)
  $core.bool get enable => $_getBF(2);
  @$pb.TagNumber(3)
  set enable($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasEnable() => $_has(2);
  @$pb.TagNumber(3)
  void clearEnable() => clearField(3);
}

class UartConfigResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'UartConfigResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  UartConfigResponse._() : super();
  factory UartConfigResponse({
    $core.bool? success,
    $core.String? error,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    return _result;
  }
  factory UartConfigResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory UartConfigResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  UartConfigResponse clone() => UartConfigResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  UartConfigResponse copyWith(void Function(UartConfigResponse) updates) => super.copyWith((message) => updates(message as UartConfigResponse)) as UartConfigResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static UartConfigResponse create() => UartConfigResponse._();
  UartConfigResponse createEmptyInstance() => create();
  static $pb.PbList<UartConfigResponse> createRepeated() => $pb.PbList<UartConfigResponse>();
  @$core.pragma('dart2js:noInline')
  static UartConfigResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<UartConfigResponse>(create);
  static UartConfigResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);
}

class UartStreamRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'UartStreamRequest', createEmptyInstance: create)
    ..a<$core.List<$core.int>>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'data', $pb.PbFieldType.OY)
    ..hasRequiredFields = false
  ;

  UartStreamRequest._() : super();
  factory UartStreamRequest({
    $core.List<$core.int>? data,
  }) {
    final _result = create();
    if (data != null) {
      _result.data = data;
    }
    return _result;
  }
  factory UartStreamRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory UartStreamRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  UartStreamRequest clone() => UartStreamRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  UartStreamRequest copyWith(void Function(UartStreamRequest) updates) => super.copyWith((message) => updates(message as UartStreamRequest)) as UartStreamRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static UartStreamRequest create() => UartStreamRequest._();
  UartStreamRequest createEmptyInstance() => create();
  static $pb.PbList<UartStreamRequest> createRepeated() => $pb.PbList<UartStreamRequest>();
  @$core.pragma('dart2js:noInline')
  static UartStreamRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<UartStreamRequest>(create);
  static UartStreamRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<$core.int> get data => $_getN(0);
  @$pb.TagNumber(1)
  set data($core.List<$core.int> v) { $_setBytes(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasData() => $_has(0);
  @$pb.TagNumber(1)
  void clearData() => clearField(1);
}

class UartStreamResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'UartStreamResponse', createEmptyInstance: create)
    ..a<$core.List<$core.int>>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'data', $pb.PbFieldType.OY)
    ..aOB(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  UartStreamResponse._() : super();
  factory UartStreamResponse({
    $core.List<$core.int>? data,
    $core.bool? success,
    $core.String? error,
  }) {
    final _result = create();
    if (data != null) {
      _result.data = data;
    }
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    return _result;
  }
  factory UartStreamResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory UartStreamResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  UartStreamResponse clone() => UartStreamResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  UartStreamResponse copyWith(void Function(UartStreamResponse) updates) => super.copyWith((message) => updates(message as UartStreamResponse)) as UartStreamResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static UartStreamResponse create() => UartStreamResponse._();
  UartStreamResponse createEmptyInstance() => create();
  static $pb.PbList<UartStreamResponse> createRepeated() => $pb.PbList<UartStreamResponse>();
  @$core.pragma('dart2js:noInline')
  static UartStreamResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<UartStreamResponse>(create);
  static UartStreamResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<$core.int> get data => $_getN(0);
  @$pb.TagNumber(1)
  set data($core.List<$core.int> v) { $_setBytes(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasData() => $_has(0);
  @$pb.TagNumber(1)
  void clearData() => clearField(1);

  @$pb.TagNumber(2)
  $core.bool get success => $_getBF(1);
  @$pb.TagNumber(2)
  set success($core.bool v) { $_setBool(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasSuccess() => $_has(1);
  @$pb.TagNumber(2)
  void clearSuccess() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get error => $_getSZ(2);
  @$pb.TagNumber(3)
  set error($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasError() => $_has(2);
  @$pb.TagNumber(3)
  void clearError() => clearField(3);
}

class ListFwFilesRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'ListFwFilesRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  ListFwFilesRequest._() : super();
  factory ListFwFilesRequest() => create();
  factory ListFwFilesRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ListFwFilesRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ListFwFilesRequest clone() => ListFwFilesRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ListFwFilesRequest copyWith(void Function(ListFwFilesRequest) updates) => super.copyWith((message) => updates(message as ListFwFilesRequest)) as ListFwFilesRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static ListFwFilesRequest create() => ListFwFilesRequest._();
  ListFwFilesRequest createEmptyInstance() => create();
  static $pb.PbList<ListFwFilesRequest> createRepeated() => $pb.PbList<ListFwFilesRequest>();
  @$core.pragma('dart2js:noInline')
  static ListFwFilesRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ListFwFilesRequest>(create);
  static ListFwFilesRequest? _defaultInstance;
}

class FwFileInfo extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'FwFileInfo', createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'name')
    ..aInt64(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'sizeKb')
    ..aOS(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'sha256Digest')
    ..hasRequiredFields = false
  ;

  FwFileInfo._() : super();
  factory FwFileInfo({
    $core.String? name,
    $fixnum.Int64? sizeKb,
    $core.String? sha256Digest,
  }) {
    final _result = create();
    if (name != null) {
      _result.name = name;
    }
    if (sizeKb != null) {
      _result.sizeKb = sizeKb;
    }
    if (sha256Digest != null) {
      _result.sha256Digest = sha256Digest;
    }
    return _result;
  }
  factory FwFileInfo.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FwFileInfo.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FwFileInfo clone() => FwFileInfo()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FwFileInfo copyWith(void Function(FwFileInfo) updates) => super.copyWith((message) => updates(message as FwFileInfo)) as FwFileInfo; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static FwFileInfo create() => FwFileInfo._();
  FwFileInfo createEmptyInstance() => create();
  static $pb.PbList<FwFileInfo> createRepeated() => $pb.PbList<FwFileInfo>();
  @$core.pragma('dart2js:noInline')
  static FwFileInfo getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FwFileInfo>(create);
  static FwFileInfo? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => clearField(1);

  @$pb.TagNumber(2)
  $fixnum.Int64 get sizeKb => $_getI64(1);
  @$pb.TagNumber(2)
  set sizeKb($fixnum.Int64 v) { $_setInt64(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasSizeKb() => $_has(1);
  @$pb.TagNumber(2)
  void clearSizeKb() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get sha256Digest => $_getSZ(2);
  @$pb.TagNumber(3)
  set sha256Digest($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasSha256Digest() => $_has(2);
  @$pb.TagNumber(3)
  void clearSha256Digest() => clearField(3);
}

class ListFwFilesResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'ListFwFilesResponse', createEmptyInstance: create)
    ..pc<FwFileInfo>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'files', $pb.PbFieldType.PM, subBuilder: FwFileInfo.create)
    ..hasRequiredFields = false
  ;

  ListFwFilesResponse._() : super();
  factory ListFwFilesResponse({
    $core.Iterable<FwFileInfo>? files,
  }) {
    final _result = create();
    if (files != null) {
      _result.files.addAll(files);
    }
    return _result;
  }
  factory ListFwFilesResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ListFwFilesResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ListFwFilesResponse clone() => ListFwFilesResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ListFwFilesResponse copyWith(void Function(ListFwFilesResponse) updates) => super.copyWith((message) => updates(message as ListFwFilesResponse)) as ListFwFilesResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static ListFwFilesResponse create() => ListFwFilesResponse._();
  ListFwFilesResponse createEmptyInstance() => create();
  static $pb.PbList<ListFwFilesResponse> createRepeated() => $pb.PbList<ListFwFilesResponse>();
  @$core.pragma('dart2js:noInline')
  static ListFwFilesResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ListFwFilesResponse>(create);
  static ListFwFilesResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<FwFileInfo> get files => $_getList(0);
}

class UploadFwFileRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'UploadFwFileRequest', createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'filename')
    ..a<$core.List<$core.int>>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'content', $pb.PbFieldType.OY)
    ..hasRequiredFields = false
  ;

  UploadFwFileRequest._() : super();
  factory UploadFwFileRequest({
    $core.String? filename,
    $core.List<$core.int>? content,
  }) {
    final _result = create();
    if (filename != null) {
      _result.filename = filename;
    }
    if (content != null) {
      _result.content = content;
    }
    return _result;
  }
  factory UploadFwFileRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory UploadFwFileRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  UploadFwFileRequest clone() => UploadFwFileRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  UploadFwFileRequest copyWith(void Function(UploadFwFileRequest) updates) => super.copyWith((message) => updates(message as UploadFwFileRequest)) as UploadFwFileRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static UploadFwFileRequest create() => UploadFwFileRequest._();
  UploadFwFileRequest createEmptyInstance() => create();
  static $pb.PbList<UploadFwFileRequest> createRepeated() => $pb.PbList<UploadFwFileRequest>();
  @$core.pragma('dart2js:noInline')
  static UploadFwFileRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<UploadFwFileRequest>(create);
  static UploadFwFileRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get filename => $_getSZ(0);
  @$pb.TagNumber(1)
  set filename($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasFilename() => $_has(0);
  @$pb.TagNumber(1)
  void clearFilename() => clearField(1);

  @$pb.TagNumber(2)
  $core.List<$core.int> get content => $_getN(1);
  @$pb.TagNumber(2)
  set content($core.List<$core.int> v) { $_setBytes(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasContent() => $_has(1);
  @$pb.TagNumber(2)
  void clearContent() => clearField(2);
}

class UploadFwFileResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'UploadFwFileResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..aOS(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'sha256Digest')
    ..hasRequiredFields = false
  ;

  UploadFwFileResponse._() : super();
  factory UploadFwFileResponse({
    $core.bool? success,
    $core.String? error,
    $core.String? sha256Digest,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (sha256Digest != null) {
      _result.sha256Digest = sha256Digest;
    }
    return _result;
  }
  factory UploadFwFileResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory UploadFwFileResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  UploadFwFileResponse clone() => UploadFwFileResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  UploadFwFileResponse copyWith(void Function(UploadFwFileResponse) updates) => super.copyWith((message) => updates(message as UploadFwFileResponse)) as UploadFwFileResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static UploadFwFileResponse create() => UploadFwFileResponse._();
  UploadFwFileResponse createEmptyInstance() => create();
  static $pb.PbList<UploadFwFileResponse> createRepeated() => $pb.PbList<UploadFwFileResponse>();
  @$core.pragma('dart2js:noInline')
  static UploadFwFileResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<UploadFwFileResponse>(create);
  static UploadFwFileResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get sha256Digest => $_getSZ(2);
  @$pb.TagNumber(3)
  set sha256Digest($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasSha256Digest() => $_has(2);
  @$pb.TagNumber(3)
  void clearSha256Digest() => clearField(3);
}

class DeleteFwFileRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DeleteFwFileRequest', createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'filename')
    ..hasRequiredFields = false
  ;

  DeleteFwFileRequest._() : super();
  factory DeleteFwFileRequest({
    $core.String? filename,
  }) {
    final _result = create();
    if (filename != null) {
      _result.filename = filename;
    }
    return _result;
  }
  factory DeleteFwFileRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DeleteFwFileRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DeleteFwFileRequest clone() => DeleteFwFileRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DeleteFwFileRequest copyWith(void Function(DeleteFwFileRequest) updates) => super.copyWith((message) => updates(message as DeleteFwFileRequest)) as DeleteFwFileRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DeleteFwFileRequest create() => DeleteFwFileRequest._();
  DeleteFwFileRequest createEmptyInstance() => create();
  static $pb.PbList<DeleteFwFileRequest> createRepeated() => $pb.PbList<DeleteFwFileRequest>();
  @$core.pragma('dart2js:noInline')
  static DeleteFwFileRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DeleteFwFileRequest>(create);
  static DeleteFwFileRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get filename => $_getSZ(0);
  @$pb.TagNumber(1)
  set filename($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasFilename() => $_has(0);
  @$pb.TagNumber(1)
  void clearFilename() => clearField(1);
}

class DeleteFwFileResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DeleteFwFileResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  DeleteFwFileResponse._() : super();
  factory DeleteFwFileResponse({
    $core.bool? success,
    $core.String? error,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    return _result;
  }
  factory DeleteFwFileResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DeleteFwFileResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DeleteFwFileResponse clone() => DeleteFwFileResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DeleteFwFileResponse copyWith(void Function(DeleteFwFileResponse) updates) => super.copyWith((message) => updates(message as DeleteFwFileResponse)) as DeleteFwFileResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DeleteFwFileResponse create() => DeleteFwFileResponse._();
  DeleteFwFileResponse createEmptyInstance() => create();
  static $pb.PbList<DeleteFwFileResponse> createRepeated() => $pb.PbList<DeleteFwFileResponse>();
  @$core.pragma('dart2js:noInline')
  static DeleteFwFileResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DeleteFwFileResponse>(create);
  static DeleteFwFileResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);
}

class FlashHexFileRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'FlashHexFileRequest', createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'fileName', protoName: 'fileName')
    ..e<DeviceType>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'device', $pb.PbFieldType.OE, defaultOrMaker: DeviceType.DEVICE_NRF9160, valueOf: DeviceType.valueOf, enumValues: DeviceType.values)
    ..aOB(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'isModemFw', protoName: 'isModemFw')
    ..hasRequiredFields = false
  ;

  FlashHexFileRequest._() : super();
  factory FlashHexFileRequest({
    $core.String? fileName,
    DeviceType? device,
    $core.bool? isModemFw,
  }) {
    final _result = create();
    if (fileName != null) {
      _result.fileName = fileName;
    }
    if (device != null) {
      _result.device = device;
    }
    if (isModemFw != null) {
      _result.isModemFw = isModemFw;
    }
    return _result;
  }
  factory FlashHexFileRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FlashHexFileRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FlashHexFileRequest clone() => FlashHexFileRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FlashHexFileRequest copyWith(void Function(FlashHexFileRequest) updates) => super.copyWith((message) => updates(message as FlashHexFileRequest)) as FlashHexFileRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static FlashHexFileRequest create() => FlashHexFileRequest._();
  FlashHexFileRequest createEmptyInstance() => create();
  static $pb.PbList<FlashHexFileRequest> createRepeated() => $pb.PbList<FlashHexFileRequest>();
  @$core.pragma('dart2js:noInline')
  static FlashHexFileRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FlashHexFileRequest>(create);
  static FlashHexFileRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get fileName => $_getSZ(0);
  @$pb.TagNumber(1)
  set fileName($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasFileName() => $_has(0);
  @$pb.TagNumber(1)
  void clearFileName() => clearField(1);

  @$pb.TagNumber(2)
  DeviceType get device => $_getN(1);
  @$pb.TagNumber(2)
  set device(DeviceType v) { setField(2, v); }
  @$pb.TagNumber(2)
  $core.bool hasDevice() => $_has(1);
  @$pb.TagNumber(2)
  void clearDevice() => clearField(2);

  @$pb.TagNumber(3)
  $core.bool get isModemFw => $_getBF(2);
  @$pb.TagNumber(3)
  set isModemFw($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasIsModemFw() => $_has(2);
  @$pb.TagNumber(3)
  void clearIsModemFw() => clearField(3);
}

class FlashHexFileResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'FlashHexFileResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'timeMs', $pb.PbFieldType.O3, protoName: 'timeMs')
    ..hasRequiredFields = false
  ;

  FlashHexFileResponse._() : super();
  factory FlashHexFileResponse({
    $core.bool? success,
    $core.String? error,
    $core.int? timeMs,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (timeMs != null) {
      _result.timeMs = timeMs;
    }
    return _result;
  }
  factory FlashHexFileResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FlashHexFileResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FlashHexFileResponse clone() => FlashHexFileResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FlashHexFileResponse copyWith(void Function(FlashHexFileResponse) updates) => super.copyWith((message) => updates(message as FlashHexFileResponse)) as FlashHexFileResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static FlashHexFileResponse create() => FlashHexFileResponse._();
  FlashHexFileResponse createEmptyInstance() => create();
  static $pb.PbList<FlashHexFileResponse> createRepeated() => $pb.PbList<FlashHexFileResponse>();
  @$core.pragma('dart2js:noInline')
  static FlashHexFileResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FlashHexFileResponse>(create);
  static FlashHexFileResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get timeMs => $_getIZ(2);
  @$pb.TagNumber(3)
  set timeMs($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasTimeMs() => $_has(2);
  @$pb.TagNumber(3)
  void clearTimeMs() => clearField(3);
}

class DutPowerEnableRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutPowerEnableRequest', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'enable')
    ..hasRequiredFields = false
  ;

  DutPowerEnableRequest._() : super();
  factory DutPowerEnableRequest({
    $core.bool? enable,
  }) {
    final _result = create();
    if (enable != null) {
      _result.enable = enable;
    }
    return _result;
  }
  factory DutPowerEnableRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutPowerEnableRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutPowerEnableRequest clone() => DutPowerEnableRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutPowerEnableRequest copyWith(void Function(DutPowerEnableRequest) updates) => super.copyWith((message) => updates(message as DutPowerEnableRequest)) as DutPowerEnableRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutPowerEnableRequest create() => DutPowerEnableRequest._();
  DutPowerEnableRequest createEmptyInstance() => create();
  static $pb.PbList<DutPowerEnableRequest> createRepeated() => $pb.PbList<DutPowerEnableRequest>();
  @$core.pragma('dart2js:noInline')
  static DutPowerEnableRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutPowerEnableRequest>(create);
  static DutPowerEnableRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get enable => $_getBF(0);
  @$pb.TagNumber(1)
  set enable($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasEnable() => $_has(0);
  @$pb.TagNumber(1)
  void clearEnable() => clearField(1);
}

class DutPowerEnableResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutPowerEnableResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  DutPowerEnableResponse._() : super();
  factory DutPowerEnableResponse({
    $core.bool? success,
    $core.String? error,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    return _result;
  }
  factory DutPowerEnableResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutPowerEnableResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutPowerEnableResponse clone() => DutPowerEnableResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutPowerEnableResponse copyWith(void Function(DutPowerEnableResponse) updates) => super.copyWith((message) => updates(message as DutPowerEnableResponse)) as DutPowerEnableResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutPowerEnableResponse create() => DutPowerEnableResponse._();
  DutPowerEnableResponse createEmptyInstance() => create();
  static $pb.PbList<DutPowerEnableResponse> createRepeated() => $pb.PbList<DutPowerEnableResponse>();
  @$core.pragma('dart2js:noInline')
  static DutPowerEnableResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutPowerEnableResponse>(create);
  static DutPowerEnableResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);
}

class DutVoltageSetRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutVoltageSetRequest', createEmptyInstance: create)
    ..a<$core.double>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voltage', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  DutVoltageSetRequest._() : super();
  factory DutVoltageSetRequest({
    $core.double? voltage,
  }) {
    final _result = create();
    if (voltage != null) {
      _result.voltage = voltage;
    }
    return _result;
  }
  factory DutVoltageSetRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutVoltageSetRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutVoltageSetRequest clone() => DutVoltageSetRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutVoltageSetRequest copyWith(void Function(DutVoltageSetRequest) updates) => super.copyWith((message) => updates(message as DutVoltageSetRequest)) as DutVoltageSetRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutVoltageSetRequest create() => DutVoltageSetRequest._();
  DutVoltageSetRequest createEmptyInstance() => create();
  static $pb.PbList<DutVoltageSetRequest> createRepeated() => $pb.PbList<DutVoltageSetRequest>();
  @$core.pragma('dart2js:noInline')
  static DutVoltageSetRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutVoltageSetRequest>(create);
  static DutVoltageSetRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.double get voltage => $_getN(0);
  @$pb.TagNumber(1)
  set voltage($core.double v) { $_setDouble(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasVoltage() => $_has(0);
  @$pb.TagNumber(1)
  void clearVoltage() => clearField(1);
}

class DutVoltageSetResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutVoltageSetResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  DutVoltageSetResponse._() : super();
  factory DutVoltageSetResponse({
    $core.bool? success,
    $core.String? error,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    return _result;
  }
  factory DutVoltageSetResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutVoltageSetResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutVoltageSetResponse clone() => DutVoltageSetResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutVoltageSetResponse copyWith(void Function(DutVoltageSetResponse) updates) => super.copyWith((message) => updates(message as DutVoltageSetResponse)) as DutVoltageSetResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutVoltageSetResponse create() => DutVoltageSetResponse._();
  DutVoltageSetResponse createEmptyInstance() => create();
  static $pb.PbList<DutVoltageSetResponse> createRepeated() => $pb.PbList<DutVoltageSetResponse>();
  @$core.pragma('dart2js:noInline')
  static DutVoltageSetResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutVoltageSetResponse>(create);
  static DutVoltageSetResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);
}

class DutCurrentReadRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutCurrentReadRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  DutCurrentReadRequest._() : super();
  factory DutCurrentReadRequest() => create();
  factory DutCurrentReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutCurrentReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutCurrentReadRequest clone() => DutCurrentReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutCurrentReadRequest copyWith(void Function(DutCurrentReadRequest) updates) => super.copyWith((message) => updates(message as DutCurrentReadRequest)) as DutCurrentReadRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutCurrentReadRequest create() => DutCurrentReadRequest._();
  DutCurrentReadRequest createEmptyInstance() => create();
  static $pb.PbList<DutCurrentReadRequest> createRepeated() => $pb.PbList<DutCurrentReadRequest>();
  @$core.pragma('dart2js:noInline')
  static DutCurrentReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutCurrentReadRequest>(create);
  static DutCurrentReadRequest? _defaultInstance;
}

class DutCurrentReadResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutCurrentReadResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'currentMa', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  DutCurrentReadResponse._() : super();
  factory DutCurrentReadResponse({
    $core.bool? success,
    $core.String? error,
    $core.int? currentMa,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (currentMa != null) {
      _result.currentMa = currentMa;
    }
    return _result;
  }
  factory DutCurrentReadResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutCurrentReadResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutCurrentReadResponse clone() => DutCurrentReadResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutCurrentReadResponse copyWith(void Function(DutCurrentReadResponse) updates) => super.copyWith((message) => updates(message as DutCurrentReadResponse)) as DutCurrentReadResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutCurrentReadResponse create() => DutCurrentReadResponse._();
  DutCurrentReadResponse createEmptyInstance() => create();
  static $pb.PbList<DutCurrentReadResponse> createRepeated() => $pb.PbList<DutCurrentReadResponse>();
  @$core.pragma('dart2js:noInline')
  static DutCurrentReadResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutCurrentReadResponse>(create);
  static DutCurrentReadResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get currentMa => $_getIZ(2);
  @$pb.TagNumber(3)
  set currentMa($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasCurrentMa() => $_has(2);
  @$pb.TagNumber(3)
  void clearCurrentMa() => clearField(3);
}

class DutVoltageReadRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutVoltageReadRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  DutVoltageReadRequest._() : super();
  factory DutVoltageReadRequest() => create();
  factory DutVoltageReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutVoltageReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutVoltageReadRequest clone() => DutVoltageReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutVoltageReadRequest copyWith(void Function(DutVoltageReadRequest) updates) => super.copyWith((message) => updates(message as DutVoltageReadRequest)) as DutVoltageReadRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutVoltageReadRequest create() => DutVoltageReadRequest._();
  DutVoltageReadRequest createEmptyInstance() => create();
  static $pb.PbList<DutVoltageReadRequest> createRepeated() => $pb.PbList<DutVoltageReadRequest>();
  @$core.pragma('dart2js:noInline')
  static DutVoltageReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutVoltageReadRequest>(create);
  static DutVoltageReadRequest? _defaultInstance;
}

class DutVoltageReadResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutVoltageReadResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voltageMv', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  DutVoltageReadResponse._() : super();
  factory DutVoltageReadResponse({
    $core.bool? success,
    $core.String? error,
    $core.int? voltageMv,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (voltageMv != null) {
      _result.voltageMv = voltageMv;
    }
    return _result;
  }
  factory DutVoltageReadResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutVoltageReadResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutVoltageReadResponse clone() => DutVoltageReadResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutVoltageReadResponse copyWith(void Function(DutVoltageReadResponse) updates) => super.copyWith((message) => updates(message as DutVoltageReadResponse)) as DutVoltageReadResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutVoltageReadResponse create() => DutVoltageReadResponse._();
  DutVoltageReadResponse createEmptyInstance() => create();
  static $pb.PbList<DutVoltageReadResponse> createRepeated() => $pb.PbList<DutVoltageReadResponse>();
  @$core.pragma('dart2js:noInline')
  static DutVoltageReadResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutVoltageReadResponse>(create);
  static DutVoltageReadResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get voltageMv => $_getIZ(2);
  @$pb.TagNumber(3)
  set voltageMv($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasVoltageMv() => $_has(2);
  @$pb.TagNumber(3)
  void clearVoltageMv() => clearField(3);
}

class DutPowerReadRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutPowerReadRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  DutPowerReadRequest._() : super();
  factory DutPowerReadRequest() => create();
  factory DutPowerReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutPowerReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutPowerReadRequest clone() => DutPowerReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutPowerReadRequest copyWith(void Function(DutPowerReadRequest) updates) => super.copyWith((message) => updates(message as DutPowerReadRequest)) as DutPowerReadRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutPowerReadRequest create() => DutPowerReadRequest._();
  DutPowerReadRequest createEmptyInstance() => create();
  static $pb.PbList<DutPowerReadRequest> createRepeated() => $pb.PbList<DutPowerReadRequest>();
  @$core.pragma('dart2js:noInline')
  static DutPowerReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutPowerReadRequest>(create);
  static DutPowerReadRequest? _defaultInstance;
}

class DutPowerReadResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutPowerReadResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'powerMw', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  DutPowerReadResponse._() : super();
  factory DutPowerReadResponse({
    $core.bool? success,
    $core.String? error,
    $core.int? powerMw,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (powerMw != null) {
      _result.powerMw = powerMw;
    }
    return _result;
  }
  factory DutPowerReadResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutPowerReadResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutPowerReadResponse clone() => DutPowerReadResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutPowerReadResponse copyWith(void Function(DutPowerReadResponse) updates) => super.copyWith((message) => updates(message as DutPowerReadResponse)) as DutPowerReadResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutPowerReadResponse create() => DutPowerReadResponse._();
  DutPowerReadResponse createEmptyInstance() => create();
  static $pb.PbList<DutPowerReadResponse> createRepeated() => $pb.PbList<DutPowerReadResponse>();
  @$core.pragma('dart2js:noInline')
  static DutPowerReadResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutPowerReadResponse>(create);
  static DutPowerReadResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get powerMw => $_getIZ(2);
  @$pb.TagNumber(3)
  set powerMw($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasPowerMw() => $_has(2);
  @$pb.TagNumber(3)
  void clearPowerMw() => clearField(3);
}

class AltimeterReadRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AltimeterReadRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  AltimeterReadRequest._() : super();
  factory AltimeterReadRequest() => create();
  factory AltimeterReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AltimeterReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AltimeterReadRequest clone() => AltimeterReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AltimeterReadRequest copyWith(void Function(AltimeterReadRequest) updates) => super.copyWith((message) => updates(message as AltimeterReadRequest)) as AltimeterReadRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AltimeterReadRequest create() => AltimeterReadRequest._();
  AltimeterReadRequest createEmptyInstance() => create();
  static $pb.PbList<AltimeterReadRequest> createRepeated() => $pb.PbList<AltimeterReadRequest>();
  @$core.pragma('dart2js:noInline')
  static AltimeterReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AltimeterReadRequest>(create);
  static AltimeterReadRequest? _defaultInstance;
}

class AltimeterReadResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AltimeterReadResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'temperatureF', $pb.PbFieldType.OD)
    ..a<$core.double>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'pressureHg', $pb.PbFieldType.OD)
    ..a<$core.double>(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'altitudeFt', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  AltimeterReadResponse._() : super();
  factory AltimeterReadResponse({
    $core.bool? success,
    $core.String? error,
    $core.double? temperatureF,
    $core.double? pressureHg,
    $core.double? altitudeFt,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (temperatureF != null) {
      _result.temperatureF = temperatureF;
    }
    if (pressureHg != null) {
      _result.pressureHg = pressureHg;
    }
    if (altitudeFt != null) {
      _result.altitudeFt = altitudeFt;
    }
    return _result;
  }
  factory AltimeterReadResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AltimeterReadResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AltimeterReadResponse clone() => AltimeterReadResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AltimeterReadResponse copyWith(void Function(AltimeterReadResponse) updates) => super.copyWith((message) => updates(message as AltimeterReadResponse)) as AltimeterReadResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AltimeterReadResponse create() => AltimeterReadResponse._();
  AltimeterReadResponse createEmptyInstance() => create();
  static $pb.PbList<AltimeterReadResponse> createRepeated() => $pb.PbList<AltimeterReadResponse>();
  @$core.pragma('dart2js:noInline')
  static AltimeterReadResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AltimeterReadResponse>(create);
  static AltimeterReadResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get temperatureF => $_getN(2);
  @$pb.TagNumber(3)
  set temperatureF($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasTemperatureF() => $_has(2);
  @$pb.TagNumber(3)
  void clearTemperatureF() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get pressureHg => $_getN(3);
  @$pb.TagNumber(4)
  set pressureHg($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasPressureHg() => $_has(3);
  @$pb.TagNumber(4)
  void clearPressureHg() => clearField(4);

  @$pb.TagNumber(5)
  $core.double get altitudeFt => $_getN(4);
  @$pb.TagNumber(5)
  set altitudeFt($core.double v) { $_setDouble(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasAltitudeFt() => $_has(4);
  @$pb.TagNumber(5)
  void clearAltitudeFt() => clearField(5);
}

class AccelReadRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AccelReadRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  AccelReadRequest._() : super();
  factory AccelReadRequest() => create();
  factory AccelReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AccelReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AccelReadRequest clone() => AccelReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AccelReadRequest copyWith(void Function(AccelReadRequest) updates) => super.copyWith((message) => updates(message as AccelReadRequest)) as AccelReadRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AccelReadRequest create() => AccelReadRequest._();
  AccelReadRequest createEmptyInstance() => create();
  static $pb.PbList<AccelReadRequest> createRepeated() => $pb.PbList<AccelReadRequest>();
  @$core.pragma('dart2js:noInline')
  static AccelReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AccelReadRequest>(create);
  static AccelReadRequest? _defaultInstance;
}

class AccelReadResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AccelReadResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'x', $pb.PbFieldType.OD)
    ..a<$core.double>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'y', $pb.PbFieldType.OD)
    ..a<$core.double>(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'z', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  AccelReadResponse._() : super();
  factory AccelReadResponse({
    $core.bool? success,
    $core.String? error,
    $core.double? x,
    $core.double? y,
    $core.double? z,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (x != null) {
      _result.x = x;
    }
    if (y != null) {
      _result.y = y;
    }
    if (z != null) {
      _result.z = z;
    }
    return _result;
  }
  factory AccelReadResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AccelReadResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AccelReadResponse clone() => AccelReadResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AccelReadResponse copyWith(void Function(AccelReadResponse) updates) => super.copyWith((message) => updates(message as AccelReadResponse)) as AccelReadResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AccelReadResponse create() => AccelReadResponse._();
  AccelReadResponse createEmptyInstance() => create();
  static $pb.PbList<AccelReadResponse> createRepeated() => $pb.PbList<AccelReadResponse>();
  @$core.pragma('dart2js:noInline')
  static AccelReadResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AccelReadResponse>(create);
  static AccelReadResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get x => $_getN(2);
  @$pb.TagNumber(3)
  set x($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasX() => $_has(2);
  @$pb.TagNumber(3)
  void clearX() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get y => $_getN(3);
  @$pb.TagNumber(4)
  set y($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasY() => $_has(3);
  @$pb.TagNumber(4)
  void clearY() => clearField(4);

  @$pb.TagNumber(5)
  $core.double get z => $_getN(4);
  @$pb.TagNumber(5)
  set z($core.double v) { $_setDouble(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasZ() => $_has(4);
  @$pb.TagNumber(5)
  void clearZ() => clearField(5);
}

class AccelReadMaxRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AccelReadMaxRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  AccelReadMaxRequest._() : super();
  factory AccelReadMaxRequest() => create();
  factory AccelReadMaxRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AccelReadMaxRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AccelReadMaxRequest clone() => AccelReadMaxRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AccelReadMaxRequest copyWith(void Function(AccelReadMaxRequest) updates) => super.copyWith((message) => updates(message as AccelReadMaxRequest)) as AccelReadMaxRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AccelReadMaxRequest create() => AccelReadMaxRequest._();
  AccelReadMaxRequest createEmptyInstance() => create();
  static $pb.PbList<AccelReadMaxRequest> createRepeated() => $pb.PbList<AccelReadMaxRequest>();
  @$core.pragma('dart2js:noInline')
  static AccelReadMaxRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AccelReadMaxRequest>(create);
  static AccelReadMaxRequest? _defaultInstance;
}

class AccelReadMaxResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AccelReadMaxResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'max', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  AccelReadMaxResponse._() : super();
  factory AccelReadMaxResponse({
    $core.bool? success,
    $core.String? error,
    $core.double? max,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (max != null) {
      _result.max = max;
    }
    return _result;
  }
  factory AccelReadMaxResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AccelReadMaxResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AccelReadMaxResponse clone() => AccelReadMaxResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AccelReadMaxResponse copyWith(void Function(AccelReadMaxResponse) updates) => super.copyWith((message) => updates(message as AccelReadMaxResponse)) as AccelReadMaxResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AccelReadMaxResponse create() => AccelReadMaxResponse._();
  AccelReadMaxResponse createEmptyInstance() => create();
  static $pb.PbList<AccelReadMaxResponse> createRepeated() => $pb.PbList<AccelReadMaxResponse>();
  @$core.pragma('dart2js:noInline')
  static AccelReadMaxResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AccelReadMaxResponse>(create);
  static AccelReadMaxResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get max => $_getN(2);
  @$pb.TagNumber(3)
  set max($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasMax() => $_has(2);
  @$pb.TagNumber(3)
  void clearMax() => clearField(3);
}

class EepromReadRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'EepromReadRequest', createEmptyInstance: create)
    ..a<$core.int>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'address', $pb.PbFieldType.O3)
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'len', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  EepromReadRequest._() : super();
  factory EepromReadRequest({
    $core.int? address,
    $core.int? len,
  }) {
    final _result = create();
    if (address != null) {
      _result.address = address;
    }
    if (len != null) {
      _result.len = len;
    }
    return _result;
  }
  factory EepromReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory EepromReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  EepromReadRequest clone() => EepromReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  EepromReadRequest copyWith(void Function(EepromReadRequest) updates) => super.copyWith((message) => updates(message as EepromReadRequest)) as EepromReadRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static EepromReadRequest create() => EepromReadRequest._();
  EepromReadRequest createEmptyInstance() => create();
  static $pb.PbList<EepromReadRequest> createRepeated() => $pb.PbList<EepromReadRequest>();
  @$core.pragma('dart2js:noInline')
  static EepromReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<EepromReadRequest>(create);
  static EepromReadRequest? _defaultInstance;

  @$pb.TagNumber(2)
  $core.int get address => $_getIZ(0);
  @$pb.TagNumber(2)
  set address($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(2)
  $core.bool hasAddress() => $_has(0);
  @$pb.TagNumber(2)
  void clearAddress() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get len => $_getIZ(1);
  @$pb.TagNumber(3)
  set len($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(3)
  $core.bool hasLen() => $_has(1);
  @$pb.TagNumber(3)
  void clearLen() => clearField(3);
}

class EepromReadResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'EepromReadResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.List<$core.int>>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'data', $pb.PbFieldType.OY)
    ..hasRequiredFields = false
  ;

  EepromReadResponse._() : super();
  factory EepromReadResponse({
    $core.bool? success,
    $core.String? error,
    $core.List<$core.int>? data,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (data != null) {
      _result.data = data;
    }
    return _result;
  }
  factory EepromReadResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory EepromReadResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  EepromReadResponse clone() => EepromReadResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  EepromReadResponse copyWith(void Function(EepromReadResponse) updates) => super.copyWith((message) => updates(message as EepromReadResponse)) as EepromReadResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static EepromReadResponse create() => EepromReadResponse._();
  EepromReadResponse createEmptyInstance() => create();
  static $pb.PbList<EepromReadResponse> createRepeated() => $pb.PbList<EepromReadResponse>();
  @$core.pragma('dart2js:noInline')
  static EepromReadResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<EepromReadResponse>(create);
  static EepromReadResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);

  @$pb.TagNumber(3)
  $core.List<$core.int> get data => $_getN(2);
  @$pb.TagNumber(3)
  set data($core.List<$core.int> v) { $_setBytes(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasData() => $_has(2);
  @$pb.TagNumber(3)
  void clearData() => clearField(3);
}

class EepromWriteRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'EepromWriteRequest', createEmptyInstance: create)
    ..a<$core.List<$core.int>>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'buffer', $pb.PbFieldType.OY)
    ..a<$core.int>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'address', $pb.PbFieldType.O3)
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'len', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  EepromWriteRequest._() : super();
  factory EepromWriteRequest({
    $core.List<$core.int>? buffer,
    $core.int? address,
    $core.int? len,
  }) {
    final _result = create();
    if (buffer != null) {
      _result.buffer = buffer;
    }
    if (address != null) {
      _result.address = address;
    }
    if (len != null) {
      _result.len = len;
    }
    return _result;
  }
  factory EepromWriteRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory EepromWriteRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  EepromWriteRequest clone() => EepromWriteRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  EepromWriteRequest copyWith(void Function(EepromWriteRequest) updates) => super.copyWith((message) => updates(message as EepromWriteRequest)) as EepromWriteRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static EepromWriteRequest create() => EepromWriteRequest._();
  EepromWriteRequest createEmptyInstance() => create();
  static $pb.PbList<EepromWriteRequest> createRepeated() => $pb.PbList<EepromWriteRequest>();
  @$core.pragma('dart2js:noInline')
  static EepromWriteRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<EepromWriteRequest>(create);
  static EepromWriteRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<$core.int> get buffer => $_getN(0);
  @$pb.TagNumber(1)
  set buffer($core.List<$core.int> v) { $_setBytes(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasBuffer() => $_has(0);
  @$pb.TagNumber(1)
  void clearBuffer() => clearField(1);

  @$pb.TagNumber(2)
  $core.int get address => $_getIZ(1);
  @$pb.TagNumber(2)
  set address($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasAddress() => $_has(1);
  @$pb.TagNumber(2)
  void clearAddress() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get len => $_getIZ(2);
  @$pb.TagNumber(3)
  set len($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLen() => $_has(2);
  @$pb.TagNumber(3)
  void clearLen() => clearField(3);
}

class EepromWriteResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'EepromWriteResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  EepromWriteResponse._() : super();
  factory EepromWriteResponse({
    $core.bool? success,
    $core.String? error,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    return _result;
  }
  factory EepromWriteResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory EepromWriteResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  EepromWriteResponse clone() => EepromWriteResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  EepromWriteResponse copyWith(void Function(EepromWriteResponse) updates) => super.copyWith((message) => updates(message as EepromWriteResponse)) as EepromWriteResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static EepromWriteResponse create() => EepromWriteResponse._();
  EepromWriteResponse createEmptyInstance() => create();
  static $pb.PbList<EepromWriteResponse> createRepeated() => $pb.PbList<EepromWriteResponse>();
  @$core.pragma('dart2js:noInline')
  static EepromWriteResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<EepromWriteResponse>(create);
  static EepromWriteResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get success => $_getBF(0);
  @$pb.TagNumber(1)
  set success($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSuccess() => $_has(0);
  @$pb.TagNumber(1)
  void clearSuccess() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get error => $_getSZ(1);
  @$pb.TagNumber(2)
  set error($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasError() => $_has(1);
  @$pb.TagNumber(2)
  void clearError() => clearField(2);
}


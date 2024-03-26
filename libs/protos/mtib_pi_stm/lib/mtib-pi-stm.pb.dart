///
//  Generated code. Do not modify.
//  source: mtib-pi-stm.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:core' as $core;

import 'package:protobuf/protobuf.dart' as $pb;

import 'mtib-pi-stm.pbenum.dart';

export 'mtib-pi-stm.pbenum.dart';

class GpioConfigurePinRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioConfigurePinRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'pinNumber', $pb.PbFieldType.O3)
    ..e<GpioDirection>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'direction', $pb.PbFieldType.OE, defaultOrMaker: GpioDirection.INPUT, valueOf: GpioDirection.valueOf, enumValues: GpioDirection.values)
    ..e<GpioConfigureResistorConfig>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'resistor', $pb.PbFieldType.OE, defaultOrMaker: GpioConfigureResistorConfig.RESISTOR_PULL_UP, valueOf: GpioConfigureResistorConfig.valueOf, enumValues: GpioConfigureResistorConfig.values)
    ..hasRequiredFields = false
  ;

  GpioConfigurePinRequest._() : super();
  factory GpioConfigurePinRequest({
    $core.int? pinNumber,
    GpioDirection? direction,
    GpioConfigureResistorConfig? resistor,
  }) {
    final _result = create();
    if (pinNumber != null) {
      _result.pinNumber = pinNumber;
    }
    if (direction != null) {
      _result.direction = direction;
    }
    if (resistor != null) {
      _result.resistor = resistor;
    }
    return _result;
  }
  factory GpioConfigurePinRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioConfigurePinRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioConfigurePinRequest clone() => GpioConfigurePinRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioConfigurePinRequest copyWith(void Function(GpioConfigurePinRequest) updates) => super.copyWith((message) => updates(message as GpioConfigurePinRequest)) as GpioConfigurePinRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioConfigurePinRequest create() => GpioConfigurePinRequest._();
  GpioConfigurePinRequest createEmptyInstance() => create();
  static $pb.PbList<GpioConfigurePinRequest> createRepeated() => $pb.PbList<GpioConfigurePinRequest>();
  @$core.pragma('dart2js:noInline')
  static GpioConfigurePinRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioConfigurePinRequest>(create);
  static GpioConfigurePinRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get pinNumber => $_getIZ(0);
  @$pb.TagNumber(1)
  set pinNumber($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPinNumber() => $_has(0);
  @$pb.TagNumber(1)
  void clearPinNumber() => clearField(1);

  @$pb.TagNumber(2)
  GpioDirection get direction => $_getN(1);
  @$pb.TagNumber(2)
  set direction(GpioDirection v) { setField(2, v); }
  @$pb.TagNumber(2)
  $core.bool hasDirection() => $_has(1);
  @$pb.TagNumber(2)
  void clearDirection() => clearField(2);

  @$pb.TagNumber(3)
  GpioConfigureResistorConfig get resistor => $_getN(2);
  @$pb.TagNumber(3)
  set resistor(GpioConfigureResistorConfig v) { setField(3, v); }
  @$pb.TagNumber(3)
  $core.bool hasResistor() => $_has(2);
  @$pb.TagNumber(3)
  void clearResistor() => clearField(3);
}

class GpioConfigurePinResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioConfigurePinResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  GpioConfigurePinResponse._() : super();
  factory GpioConfigurePinResponse({
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
  factory GpioConfigurePinResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioConfigurePinResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioConfigurePinResponse clone() => GpioConfigurePinResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioConfigurePinResponse copyWith(void Function(GpioConfigurePinResponse) updates) => super.copyWith((message) => updates(message as GpioConfigurePinResponse)) as GpioConfigurePinResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioConfigurePinResponse create() => GpioConfigurePinResponse._();
  GpioConfigurePinResponse createEmptyInstance() => create();
  static $pb.PbList<GpioConfigurePinResponse> createRepeated() => $pb.PbList<GpioConfigurePinResponse>();
  @$core.pragma('dart2js:noInline')
  static GpioConfigurePinResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioConfigurePinResponse>(create);
  static GpioConfigurePinResponse? _defaultInstance;

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

class GpioSetPinRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioSetPinRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'pinNumber', $pb.PbFieldType.O3)
    ..e<GpioValue>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'value', $pb.PbFieldType.OE, defaultOrMaker: GpioValue.LOW, valueOf: GpioValue.valueOf, enumValues: GpioValue.values)
    ..hasRequiredFields = false
  ;

  GpioSetPinRequest._() : super();
  factory GpioSetPinRequest({
    $core.int? pinNumber,
    GpioValue? value,
  }) {
    final _result = create();
    if (pinNumber != null) {
      _result.pinNumber = pinNumber;
    }
    if (value != null) {
      _result.value = value;
    }
    return _result;
  }
  factory GpioSetPinRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioSetPinRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioSetPinRequest clone() => GpioSetPinRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioSetPinRequest copyWith(void Function(GpioSetPinRequest) updates) => super.copyWith((message) => updates(message as GpioSetPinRequest)) as GpioSetPinRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioSetPinRequest create() => GpioSetPinRequest._();
  GpioSetPinRequest createEmptyInstance() => create();
  static $pb.PbList<GpioSetPinRequest> createRepeated() => $pb.PbList<GpioSetPinRequest>();
  @$core.pragma('dart2js:noInline')
  static GpioSetPinRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioSetPinRequest>(create);
  static GpioSetPinRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get pinNumber => $_getIZ(0);
  @$pb.TagNumber(1)
  set pinNumber($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPinNumber() => $_has(0);
  @$pb.TagNumber(1)
  void clearPinNumber() => clearField(1);

  @$pb.TagNumber(2)
  GpioValue get value => $_getN(1);
  @$pb.TagNumber(2)
  set value(GpioValue v) { setField(2, v); }
  @$pb.TagNumber(2)
  $core.bool hasValue() => $_has(1);
  @$pb.TagNumber(2)
  void clearValue() => clearField(2);
}

class GpioSetPinResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioSetPinResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  GpioSetPinResponse._() : super();
  factory GpioSetPinResponse({
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
  factory GpioSetPinResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioSetPinResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioSetPinResponse clone() => GpioSetPinResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioSetPinResponse copyWith(void Function(GpioSetPinResponse) updates) => super.copyWith((message) => updates(message as GpioSetPinResponse)) as GpioSetPinResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioSetPinResponse create() => GpioSetPinResponse._();
  GpioSetPinResponse createEmptyInstance() => create();
  static $pb.PbList<GpioSetPinResponse> createRepeated() => $pb.PbList<GpioSetPinResponse>();
  @$core.pragma('dart2js:noInline')
  static GpioSetPinResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioSetPinResponse>(create);
  static GpioSetPinResponse? _defaultInstance;

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

class GpioReadPinRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioReadPinRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'pinNumber', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  GpioReadPinRequest._() : super();
  factory GpioReadPinRequest({
    $core.int? pinNumber,
  }) {
    final _result = create();
    if (pinNumber != null) {
      _result.pinNumber = pinNumber;
    }
    return _result;
  }
  factory GpioReadPinRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioReadPinRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioReadPinRequest clone() => GpioReadPinRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioReadPinRequest copyWith(void Function(GpioReadPinRequest) updates) => super.copyWith((message) => updates(message as GpioReadPinRequest)) as GpioReadPinRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioReadPinRequest create() => GpioReadPinRequest._();
  GpioReadPinRequest createEmptyInstance() => create();
  static $pb.PbList<GpioReadPinRequest> createRepeated() => $pb.PbList<GpioReadPinRequest>();
  @$core.pragma('dart2js:noInline')
  static GpioReadPinRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioReadPinRequest>(create);
  static GpioReadPinRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get pinNumber => $_getIZ(0);
  @$pb.TagNumber(1)
  set pinNumber($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPinNumber() => $_has(0);
  @$pb.TagNumber(1)
  void clearPinNumber() => clearField(1);
}

class GpioReadPinResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'GpioReadPinResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..e<GpioValue>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'value', $pb.PbFieldType.OE, defaultOrMaker: GpioValue.LOW, valueOf: GpioValue.valueOf, enumValues: GpioValue.values)
    ..hasRequiredFields = false
  ;

  GpioReadPinResponse._() : super();
  factory GpioReadPinResponse({
    $core.bool? success,
    $core.String? error,
    GpioValue? value,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (value != null) {
      _result.value = value;
    }
    return _result;
  }
  factory GpioReadPinResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GpioReadPinResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GpioReadPinResponse clone() => GpioReadPinResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GpioReadPinResponse copyWith(void Function(GpioReadPinResponse) updates) => super.copyWith((message) => updates(message as GpioReadPinResponse)) as GpioReadPinResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static GpioReadPinResponse create() => GpioReadPinResponse._();
  GpioReadPinResponse createEmptyInstance() => create();
  static $pb.PbList<GpioReadPinResponse> createRepeated() => $pb.PbList<GpioReadPinResponse>();
  @$core.pragma('dart2js:noInline')
  static GpioReadPinResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GpioReadPinResponse>(create);
  static GpioReadPinResponse? _defaultInstance;

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
  GpioValue get value => $_getN(2);
  @$pb.TagNumber(3)
  set value(GpioValue v) { setField(3, v); }
  @$pb.TagNumber(3)
  $core.bool hasValue() => $_has(2);
  @$pb.TagNumber(3)
  void clearValue() => clearField(3);
}

class AdcReadChannelRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdcReadChannelRequest', createEmptyInstance: create)
    ..e<ChannelNumber>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'channelNumber', $pb.PbFieldType.OE, defaultOrMaker: ChannelNumber.CHANNEL_0, valueOf: ChannelNumber.valueOf, enumValues: ChannelNumber.values)
    ..a<$core.int>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'delayMs', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  AdcReadChannelRequest._() : super();
  factory AdcReadChannelRequest({
    ChannelNumber? channelNumber,
    $core.int? delayMs,
  }) {
    final _result = create();
    if (channelNumber != null) {
      _result.channelNumber = channelNumber;
    }
    if (delayMs != null) {
      _result.delayMs = delayMs;
    }
    return _result;
  }
  factory AdcReadChannelRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdcReadChannelRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdcReadChannelRequest clone() => AdcReadChannelRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdcReadChannelRequest copyWith(void Function(AdcReadChannelRequest) updates) => super.copyWith((message) => updates(message as AdcReadChannelRequest)) as AdcReadChannelRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdcReadChannelRequest create() => AdcReadChannelRequest._();
  AdcReadChannelRequest createEmptyInstance() => create();
  static $pb.PbList<AdcReadChannelRequest> createRepeated() => $pb.PbList<AdcReadChannelRequest>();
  @$core.pragma('dart2js:noInline')
  static AdcReadChannelRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdcReadChannelRequest>(create);
  static AdcReadChannelRequest? _defaultInstance;

  @$pb.TagNumber(1)
  ChannelNumber get channelNumber => $_getN(0);
  @$pb.TagNumber(1)
  set channelNumber(ChannelNumber v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasChannelNumber() => $_has(0);
  @$pb.TagNumber(1)
  void clearChannelNumber() => clearField(1);

  @$pb.TagNumber(2)
  $core.int get delayMs => $_getIZ(1);
  @$pb.TagNumber(2)
  set delayMs($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDelayMs() => $_has(1);
  @$pb.TagNumber(2)
  void clearDelayMs() => clearField(2);
}

class AdcReadChannelResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdcReadChannelResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voltage', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  AdcReadChannelResponse._() : super();
  factory AdcReadChannelResponse({
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
  factory AdcReadChannelResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdcReadChannelResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdcReadChannelResponse clone() => AdcReadChannelResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdcReadChannelResponse copyWith(void Function(AdcReadChannelResponse) updates) => super.copyWith((message) => updates(message as AdcReadChannelResponse)) as AdcReadChannelResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdcReadChannelResponse create() => AdcReadChannelResponse._();
  AdcReadChannelResponse createEmptyInstance() => create();
  static $pb.PbList<AdcReadChannelResponse> createRepeated() => $pb.PbList<AdcReadChannelResponse>();
  @$core.pragma('dart2js:noInline')
  static AdcReadChannelResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdcReadChannelResponse>(create);
  static AdcReadChannelResponse? _defaultInstance;

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

class AdcReadAllChannelsRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdcReadAllChannelsRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'delayMs', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  AdcReadAllChannelsRequest._() : super();
  factory AdcReadAllChannelsRequest({
    $core.int? delayMs,
  }) {
    final _result = create();
    if (delayMs != null) {
      _result.delayMs = delayMs;
    }
    return _result;
  }
  factory AdcReadAllChannelsRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdcReadAllChannelsRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdcReadAllChannelsRequest clone() => AdcReadAllChannelsRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdcReadAllChannelsRequest copyWith(void Function(AdcReadAllChannelsRequest) updates) => super.copyWith((message) => updates(message as AdcReadAllChannelsRequest)) as AdcReadAllChannelsRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdcReadAllChannelsRequest create() => AdcReadAllChannelsRequest._();
  AdcReadAllChannelsRequest createEmptyInstance() => create();
  static $pb.PbList<AdcReadAllChannelsRequest> createRepeated() => $pb.PbList<AdcReadAllChannelsRequest>();
  @$core.pragma('dart2js:noInline')
  static AdcReadAllChannelsRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdcReadAllChannelsRequest>(create);
  static AdcReadAllChannelsRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get delayMs => $_getIZ(0);
  @$pb.TagNumber(1)
  set delayMs($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasDelayMs() => $_has(0);
  @$pb.TagNumber(1)
  void clearDelayMs() => clearField(1);
}

class AdcReadAllChannelsResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdcReadAllChannelsResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..p<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voltage', $pb.PbFieldType.KD)
    ..hasRequiredFields = false
  ;

  AdcReadAllChannelsResponse._() : super();
  factory AdcReadAllChannelsResponse({
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
  factory AdcReadAllChannelsResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdcReadAllChannelsResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdcReadAllChannelsResponse clone() => AdcReadAllChannelsResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdcReadAllChannelsResponse copyWith(void Function(AdcReadAllChannelsResponse) updates) => super.copyWith((message) => updates(message as AdcReadAllChannelsResponse)) as AdcReadAllChannelsResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdcReadAllChannelsResponse create() => AdcReadAllChannelsResponse._();
  AdcReadAllChannelsResponse createEmptyInstance() => create();
  static $pb.PbList<AdcReadAllChannelsResponse> createRepeated() => $pb.PbList<AdcReadAllChannelsResponse>();
  @$core.pragma('dart2js:noInline')
  static AdcReadAllChannelsResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdcReadAllChannelsResponse>(create);
  static AdcReadAllChannelsResponse? _defaultInstance;

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

class Bmp390ReadValuesRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Bmp390ReadValuesRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  Bmp390ReadValuesRequest._() : super();
  factory Bmp390ReadValuesRequest() => create();
  factory Bmp390ReadValuesRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Bmp390ReadValuesRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Bmp390ReadValuesRequest clone() => Bmp390ReadValuesRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Bmp390ReadValuesRequest copyWith(void Function(Bmp390ReadValuesRequest) updates) => super.copyWith((message) => updates(message as Bmp390ReadValuesRequest)) as Bmp390ReadValuesRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Bmp390ReadValuesRequest create() => Bmp390ReadValuesRequest._();
  Bmp390ReadValuesRequest createEmptyInstance() => create();
  static $pb.PbList<Bmp390ReadValuesRequest> createRepeated() => $pb.PbList<Bmp390ReadValuesRequest>();
  @$core.pragma('dart2js:noInline')
  static Bmp390ReadValuesRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Bmp390ReadValuesRequest>(create);
  static Bmp390ReadValuesRequest? _defaultInstance;
}

class Bmp390ReadValuesResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Bmp390ReadValuesResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'temperatureF', $pb.PbFieldType.OD)
    ..a<$core.double>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'pressureHg', $pb.PbFieldType.OD)
    ..a<$core.double>(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'altitudeFt', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  Bmp390ReadValuesResponse._() : super();
  factory Bmp390ReadValuesResponse({
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
  factory Bmp390ReadValuesResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Bmp390ReadValuesResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Bmp390ReadValuesResponse clone() => Bmp390ReadValuesResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Bmp390ReadValuesResponse copyWith(void Function(Bmp390ReadValuesResponse) updates) => super.copyWith((message) => updates(message as Bmp390ReadValuesResponse)) as Bmp390ReadValuesResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Bmp390ReadValuesResponse create() => Bmp390ReadValuesResponse._();
  Bmp390ReadValuesResponse createEmptyInstance() => create();
  static $pb.PbList<Bmp390ReadValuesResponse> createRepeated() => $pb.PbList<Bmp390ReadValuesResponse>();
  @$core.pragma('dart2js:noInline')
  static Bmp390ReadValuesResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Bmp390ReadValuesResponse>(create);
  static Bmp390ReadValuesResponse? _defaultInstance;

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

class Lis2de12ReadValuesRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Lis2de12ReadValuesRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  Lis2de12ReadValuesRequest._() : super();
  factory Lis2de12ReadValuesRequest() => create();
  factory Lis2de12ReadValuesRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Lis2de12ReadValuesRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Lis2de12ReadValuesRequest clone() => Lis2de12ReadValuesRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Lis2de12ReadValuesRequest copyWith(void Function(Lis2de12ReadValuesRequest) updates) => super.copyWith((message) => updates(message as Lis2de12ReadValuesRequest)) as Lis2de12ReadValuesRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Lis2de12ReadValuesRequest create() => Lis2de12ReadValuesRequest._();
  Lis2de12ReadValuesRequest createEmptyInstance() => create();
  static $pb.PbList<Lis2de12ReadValuesRequest> createRepeated() => $pb.PbList<Lis2de12ReadValuesRequest>();
  @$core.pragma('dart2js:noInline')
  static Lis2de12ReadValuesRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Lis2de12ReadValuesRequest>(create);
  static Lis2de12ReadValuesRequest? _defaultInstance;
}

class Lis2de12ReadValuesResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Lis2de12ReadValuesResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'xValue', $pb.PbFieldType.OD)
    ..a<$core.double>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'yValue', $pb.PbFieldType.OD)
    ..a<$core.double>(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'zValue', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  Lis2de12ReadValuesResponse._() : super();
  factory Lis2de12ReadValuesResponse({
    $core.bool? success,
    $core.String? error,
    $core.double? xValue,
    $core.double? yValue,
    $core.double? zValue,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (xValue != null) {
      _result.xValue = xValue;
    }
    if (yValue != null) {
      _result.yValue = yValue;
    }
    if (zValue != null) {
      _result.zValue = zValue;
    }
    return _result;
  }
  factory Lis2de12ReadValuesResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Lis2de12ReadValuesResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Lis2de12ReadValuesResponse clone() => Lis2de12ReadValuesResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Lis2de12ReadValuesResponse copyWith(void Function(Lis2de12ReadValuesResponse) updates) => super.copyWith((message) => updates(message as Lis2de12ReadValuesResponse)) as Lis2de12ReadValuesResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Lis2de12ReadValuesResponse create() => Lis2de12ReadValuesResponse._();
  Lis2de12ReadValuesResponse createEmptyInstance() => create();
  static $pb.PbList<Lis2de12ReadValuesResponse> createRepeated() => $pb.PbList<Lis2de12ReadValuesResponse>();
  @$core.pragma('dart2js:noInline')
  static Lis2de12ReadValuesResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Lis2de12ReadValuesResponse>(create);
  static Lis2de12ReadValuesResponse? _defaultInstance;

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
  $core.double get xValue => $_getN(2);
  @$pb.TagNumber(3)
  set xValue($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasXValue() => $_has(2);
  @$pb.TagNumber(3)
  void clearXValue() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get yValue => $_getN(3);
  @$pb.TagNumber(4)
  set yValue($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasYValue() => $_has(3);
  @$pb.TagNumber(4)
  void clearYValue() => clearField(4);

  @$pb.TagNumber(5)
  $core.double get zValue => $_getN(4);
  @$pb.TagNumber(5)
  set zValue($core.double v) { $_setDouble(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasZValue() => $_has(4);
  @$pb.TagNumber(5)
  void clearZValue() => clearField(5);
}

class Lis2de12ReadMaxForceRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Lis2de12ReadMaxForceRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  Lis2de12ReadMaxForceRequest._() : super();
  factory Lis2de12ReadMaxForceRequest() => create();
  factory Lis2de12ReadMaxForceRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Lis2de12ReadMaxForceRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Lis2de12ReadMaxForceRequest clone() => Lis2de12ReadMaxForceRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Lis2de12ReadMaxForceRequest copyWith(void Function(Lis2de12ReadMaxForceRequest) updates) => super.copyWith((message) => updates(message as Lis2de12ReadMaxForceRequest)) as Lis2de12ReadMaxForceRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Lis2de12ReadMaxForceRequest create() => Lis2de12ReadMaxForceRequest._();
  Lis2de12ReadMaxForceRequest createEmptyInstance() => create();
  static $pb.PbList<Lis2de12ReadMaxForceRequest> createRepeated() => $pb.PbList<Lis2de12ReadMaxForceRequest>();
  @$core.pragma('dart2js:noInline')
  static Lis2de12ReadMaxForceRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Lis2de12ReadMaxForceRequest>(create);
  static Lis2de12ReadMaxForceRequest? _defaultInstance;
}

class Lis2de12ReadMaxForceResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Lis2de12ReadMaxForceResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'maxForce', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  Lis2de12ReadMaxForceResponse._() : super();
  factory Lis2de12ReadMaxForceResponse({
    $core.bool? success,
    $core.String? error,
    $core.double? maxForce,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (maxForce != null) {
      _result.maxForce = maxForce;
    }
    return _result;
  }
  factory Lis2de12ReadMaxForceResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Lis2de12ReadMaxForceResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Lis2de12ReadMaxForceResponse clone() => Lis2de12ReadMaxForceResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Lis2de12ReadMaxForceResponse copyWith(void Function(Lis2de12ReadMaxForceResponse) updates) => super.copyWith((message) => updates(message as Lis2de12ReadMaxForceResponse)) as Lis2de12ReadMaxForceResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Lis2de12ReadMaxForceResponse create() => Lis2de12ReadMaxForceResponse._();
  Lis2de12ReadMaxForceResponse createEmptyInstance() => create();
  static $pb.PbList<Lis2de12ReadMaxForceResponse> createRepeated() => $pb.PbList<Lis2de12ReadMaxForceResponse>();
  @$core.pragma('dart2js:noInline')
  static Lis2de12ReadMaxForceResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Lis2de12ReadMaxForceResponse>(create);
  static Lis2de12ReadMaxForceResponse? _defaultInstance;

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
  $core.double get maxForce => $_getN(2);
  @$pb.TagNumber(3)
  set maxForce($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasMaxForce() => $_has(2);
  @$pb.TagNumber(3)
  void clearMaxForce() => clearField(3);
}

class EepromWriteToMemRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'EepromWriteToMemRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'address', $pb.PbFieldType.O3)
    ..a<$core.List<$core.int>>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'data', $pb.PbFieldType.OY)
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'len', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  EepromWriteToMemRequest._() : super();
  factory EepromWriteToMemRequest({
    $core.int? address,
    $core.List<$core.int>? data,
    $core.int? len,
  }) {
    final _result = create();
    if (address != null) {
      _result.address = address;
    }
    if (data != null) {
      _result.data = data;
    }
    if (len != null) {
      _result.len = len;
    }
    return _result;
  }
  factory EepromWriteToMemRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory EepromWriteToMemRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  EepromWriteToMemRequest clone() => EepromWriteToMemRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  EepromWriteToMemRequest copyWith(void Function(EepromWriteToMemRequest) updates) => super.copyWith((message) => updates(message as EepromWriteToMemRequest)) as EepromWriteToMemRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static EepromWriteToMemRequest create() => EepromWriteToMemRequest._();
  EepromWriteToMemRequest createEmptyInstance() => create();
  static $pb.PbList<EepromWriteToMemRequest> createRepeated() => $pb.PbList<EepromWriteToMemRequest>();
  @$core.pragma('dart2js:noInline')
  static EepromWriteToMemRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<EepromWriteToMemRequest>(create);
  static EepromWriteToMemRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get address => $_getIZ(0);
  @$pb.TagNumber(1)
  set address($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasAddress() => $_has(0);
  @$pb.TagNumber(1)
  void clearAddress() => clearField(1);

  @$pb.TagNumber(2)
  $core.List<$core.int> get data => $_getN(1);
  @$pb.TagNumber(2)
  set data($core.List<$core.int> v) { $_setBytes(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasData() => $_has(1);
  @$pb.TagNumber(2)
  void clearData() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get len => $_getIZ(2);
  @$pb.TagNumber(3)
  set len($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLen() => $_has(2);
  @$pb.TagNumber(3)
  void clearLen() => clearField(3);
}

class EepromWriteToMemResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'EepromWriteToMemResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  EepromWriteToMemResponse._() : super();
  factory EepromWriteToMemResponse({
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
  factory EepromWriteToMemResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory EepromWriteToMemResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  EepromWriteToMemResponse clone() => EepromWriteToMemResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  EepromWriteToMemResponse copyWith(void Function(EepromWriteToMemResponse) updates) => super.copyWith((message) => updates(message as EepromWriteToMemResponse)) as EepromWriteToMemResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static EepromWriteToMemResponse create() => EepromWriteToMemResponse._();
  EepromWriteToMemResponse createEmptyInstance() => create();
  static $pb.PbList<EepromWriteToMemResponse> createRepeated() => $pb.PbList<EepromWriteToMemResponse>();
  @$core.pragma('dart2js:noInline')
  static EepromWriteToMemResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<EepromWriteToMemResponse>(create);
  static EepromWriteToMemResponse? _defaultInstance;

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

class EepromReadFromMemRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'EepromReadFromMemRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'address', $pb.PbFieldType.O3)
    ..a<$core.int>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'len', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  EepromReadFromMemRequest._() : super();
  factory EepromReadFromMemRequest({
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
  factory EepromReadFromMemRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory EepromReadFromMemRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  EepromReadFromMemRequest clone() => EepromReadFromMemRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  EepromReadFromMemRequest copyWith(void Function(EepromReadFromMemRequest) updates) => super.copyWith((message) => updates(message as EepromReadFromMemRequest)) as EepromReadFromMemRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static EepromReadFromMemRequest create() => EepromReadFromMemRequest._();
  EepromReadFromMemRequest createEmptyInstance() => create();
  static $pb.PbList<EepromReadFromMemRequest> createRepeated() => $pb.PbList<EepromReadFromMemRequest>();
  @$core.pragma('dart2js:noInline')
  static EepromReadFromMemRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<EepromReadFromMemRequest>(create);
  static EepromReadFromMemRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get address => $_getIZ(0);
  @$pb.TagNumber(1)
  set address($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasAddress() => $_has(0);
  @$pb.TagNumber(1)
  void clearAddress() => clearField(1);

  @$pb.TagNumber(2)
  $core.int get len => $_getIZ(1);
  @$pb.TagNumber(2)
  set len($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasLen() => $_has(1);
  @$pb.TagNumber(2)
  void clearLen() => clearField(2);
}

class EepromReadFromMemResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'EepromReadFromMemResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.List<$core.int>>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'data', $pb.PbFieldType.OY)
    ..hasRequiredFields = false
  ;

  EepromReadFromMemResponse._() : super();
  factory EepromReadFromMemResponse({
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
  factory EepromReadFromMemResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory EepromReadFromMemResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  EepromReadFromMemResponse clone() => EepromReadFromMemResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  EepromReadFromMemResponse copyWith(void Function(EepromReadFromMemResponse) updates) => super.copyWith((message) => updates(message as EepromReadFromMemResponse)) as EepromReadFromMemResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static EepromReadFromMemResponse create() => EepromReadFromMemResponse._();
  EepromReadFromMemResponse createEmptyInstance() => create();
  static $pb.PbList<EepromReadFromMemResponse> createRepeated() => $pb.PbList<EepromReadFromMemResponse>();
  @$core.pragma('dart2js:noInline')
  static EepromReadFromMemResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<EepromReadFromMemResponse>(create);
  static EepromReadFromMemResponse? _defaultInstance;

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

class Ina219ReadCurrentRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Ina219ReadCurrentRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  Ina219ReadCurrentRequest._() : super();
  factory Ina219ReadCurrentRequest() => create();
  factory Ina219ReadCurrentRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Ina219ReadCurrentRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Ina219ReadCurrentRequest clone() => Ina219ReadCurrentRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Ina219ReadCurrentRequest copyWith(void Function(Ina219ReadCurrentRequest) updates) => super.copyWith((message) => updates(message as Ina219ReadCurrentRequest)) as Ina219ReadCurrentRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Ina219ReadCurrentRequest create() => Ina219ReadCurrentRequest._();
  Ina219ReadCurrentRequest createEmptyInstance() => create();
  static $pb.PbList<Ina219ReadCurrentRequest> createRepeated() => $pb.PbList<Ina219ReadCurrentRequest>();
  @$core.pragma('dart2js:noInline')
  static Ina219ReadCurrentRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Ina219ReadCurrentRequest>(create);
  static Ina219ReadCurrentRequest? _defaultInstance;
}

class Ina219ReadCurrentResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Ina219ReadCurrentResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'currentValueMa', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  Ina219ReadCurrentResponse._() : super();
  factory Ina219ReadCurrentResponse({
    $core.bool? success,
    $core.String? error,
    $core.int? currentValueMa,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (currentValueMa != null) {
      _result.currentValueMa = currentValueMa;
    }
    return _result;
  }
  factory Ina219ReadCurrentResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Ina219ReadCurrentResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Ina219ReadCurrentResponse clone() => Ina219ReadCurrentResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Ina219ReadCurrentResponse copyWith(void Function(Ina219ReadCurrentResponse) updates) => super.copyWith((message) => updates(message as Ina219ReadCurrentResponse)) as Ina219ReadCurrentResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Ina219ReadCurrentResponse create() => Ina219ReadCurrentResponse._();
  Ina219ReadCurrentResponse createEmptyInstance() => create();
  static $pb.PbList<Ina219ReadCurrentResponse> createRepeated() => $pb.PbList<Ina219ReadCurrentResponse>();
  @$core.pragma('dart2js:noInline')
  static Ina219ReadCurrentResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Ina219ReadCurrentResponse>(create);
  static Ina219ReadCurrentResponse? _defaultInstance;

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
  $core.int get currentValueMa => $_getIZ(2);
  @$pb.TagNumber(3)
  set currentValueMa($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasCurrentValueMa() => $_has(2);
  @$pb.TagNumber(3)
  void clearCurrentValueMa() => clearField(3);
}

class Ina219ReadVoltageRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Ina219ReadVoltageRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  Ina219ReadVoltageRequest._() : super();
  factory Ina219ReadVoltageRequest() => create();
  factory Ina219ReadVoltageRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Ina219ReadVoltageRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Ina219ReadVoltageRequest clone() => Ina219ReadVoltageRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Ina219ReadVoltageRequest copyWith(void Function(Ina219ReadVoltageRequest) updates) => super.copyWith((message) => updates(message as Ina219ReadVoltageRequest)) as Ina219ReadVoltageRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Ina219ReadVoltageRequest create() => Ina219ReadVoltageRequest._();
  Ina219ReadVoltageRequest createEmptyInstance() => create();
  static $pb.PbList<Ina219ReadVoltageRequest> createRepeated() => $pb.PbList<Ina219ReadVoltageRequest>();
  @$core.pragma('dart2js:noInline')
  static Ina219ReadVoltageRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Ina219ReadVoltageRequest>(create);
  static Ina219ReadVoltageRequest? _defaultInstance;
}

class Ina219ReadVoltageResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Ina219ReadVoltageResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voltageValueMv', $pb.PbFieldType.OU3)
    ..hasRequiredFields = false
  ;

  Ina219ReadVoltageResponse._() : super();
  factory Ina219ReadVoltageResponse({
    $core.bool? success,
    $core.String? error,
    $core.int? voltageValueMv,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (voltageValueMv != null) {
      _result.voltageValueMv = voltageValueMv;
    }
    return _result;
  }
  factory Ina219ReadVoltageResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Ina219ReadVoltageResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Ina219ReadVoltageResponse clone() => Ina219ReadVoltageResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Ina219ReadVoltageResponse copyWith(void Function(Ina219ReadVoltageResponse) updates) => super.copyWith((message) => updates(message as Ina219ReadVoltageResponse)) as Ina219ReadVoltageResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Ina219ReadVoltageResponse create() => Ina219ReadVoltageResponse._();
  Ina219ReadVoltageResponse createEmptyInstance() => create();
  static $pb.PbList<Ina219ReadVoltageResponse> createRepeated() => $pb.PbList<Ina219ReadVoltageResponse>();
  @$core.pragma('dart2js:noInline')
  static Ina219ReadVoltageResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Ina219ReadVoltageResponse>(create);
  static Ina219ReadVoltageResponse? _defaultInstance;

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
  $core.int get voltageValueMv => $_getIZ(2);
  @$pb.TagNumber(3)
  set voltageValueMv($core.int v) { $_setUnsignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasVoltageValueMv() => $_has(2);
  @$pb.TagNumber(3)
  void clearVoltageValueMv() => clearField(3);
}

class Ina219ReadPowerRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Ina219ReadPowerRequest', createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  Ina219ReadPowerRequest._() : super();
  factory Ina219ReadPowerRequest() => create();
  factory Ina219ReadPowerRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Ina219ReadPowerRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Ina219ReadPowerRequest clone() => Ina219ReadPowerRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Ina219ReadPowerRequest copyWith(void Function(Ina219ReadPowerRequest) updates) => super.copyWith((message) => updates(message as Ina219ReadPowerRequest)) as Ina219ReadPowerRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Ina219ReadPowerRequest create() => Ina219ReadPowerRequest._();
  Ina219ReadPowerRequest createEmptyInstance() => create();
  static $pb.PbList<Ina219ReadPowerRequest> createRepeated() => $pb.PbList<Ina219ReadPowerRequest>();
  @$core.pragma('dart2js:noInline')
  static Ina219ReadPowerRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Ina219ReadPowerRequest>(create);
  static Ina219ReadPowerRequest? _defaultInstance;
}

class Ina219ReadPowerResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Ina219ReadPowerResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..a<$core.int>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'powerValueMw', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  Ina219ReadPowerResponse._() : super();
  factory Ina219ReadPowerResponse({
    $core.bool? success,
    $core.String? error,
    $core.int? powerValueMw,
  }) {
    final _result = create();
    if (success != null) {
      _result.success = success;
    }
    if (error != null) {
      _result.error = error;
    }
    if (powerValueMw != null) {
      _result.powerValueMw = powerValueMw;
    }
    return _result;
  }
  factory Ina219ReadPowerResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Ina219ReadPowerResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Ina219ReadPowerResponse clone() => Ina219ReadPowerResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Ina219ReadPowerResponse copyWith(void Function(Ina219ReadPowerResponse) updates) => super.copyWith((message) => updates(message as Ina219ReadPowerResponse)) as Ina219ReadPowerResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Ina219ReadPowerResponse create() => Ina219ReadPowerResponse._();
  Ina219ReadPowerResponse createEmptyInstance() => create();
  static $pb.PbList<Ina219ReadPowerResponse> createRepeated() => $pb.PbList<Ina219ReadPowerResponse>();
  @$core.pragma('dart2js:noInline')
  static Ina219ReadPowerResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Ina219ReadPowerResponse>(create);
  static Ina219ReadPowerResponse? _defaultInstance;

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
  $core.int get powerValueMw => $_getIZ(2);
  @$pb.TagNumber(3)
  set powerValueMw($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasPowerValueMw() => $_has(2);
  @$pb.TagNumber(3)
  void clearPowerValueMw() => clearField(3);
}

class UartMessageRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'UartMessageRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'uartPort', $pb.PbFieldType.OU3)
    ..a<$core.List<$core.int>>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'data', $pb.PbFieldType.OY)
    ..hasRequiredFields = false
  ;

  UartMessageRequest._() : super();
  factory UartMessageRequest({
    $core.int? uartPort,
    $core.List<$core.int>? data,
  }) {
    final _result = create();
    if (uartPort != null) {
      _result.uartPort = uartPort;
    }
    if (data != null) {
      _result.data = data;
    }
    return _result;
  }
  factory UartMessageRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory UartMessageRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  UartMessageRequest clone() => UartMessageRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  UartMessageRequest copyWith(void Function(UartMessageRequest) updates) => super.copyWith((message) => updates(message as UartMessageRequest)) as UartMessageRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static UartMessageRequest create() => UartMessageRequest._();
  UartMessageRequest createEmptyInstance() => create();
  static $pb.PbList<UartMessageRequest> createRepeated() => $pb.PbList<UartMessageRequest>();
  @$core.pragma('dart2js:noInline')
  static UartMessageRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<UartMessageRequest>(create);
  static UartMessageRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get uartPort => $_getIZ(0);
  @$pb.TagNumber(1)
  set uartPort($core.int v) { $_setUnsignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasUartPort() => $_has(0);
  @$pb.TagNumber(1)
  void clearUartPort() => clearField(1);

  @$pb.TagNumber(2)
  $core.List<$core.int> get data => $_getN(1);
  @$pb.TagNumber(2)
  set data($core.List<$core.int> v) { $_setBytes(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasData() => $_has(1);
  @$pb.TagNumber(2)
  void clearData() => clearField(2);
}

class UartMessageResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'UartMessageResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  UartMessageResponse._() : super();
  factory UartMessageResponse({
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
  factory UartMessageResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory UartMessageResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  UartMessageResponse clone() => UartMessageResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  UartMessageResponse copyWith(void Function(UartMessageResponse) updates) => super.copyWith((message) => updates(message as UartMessageResponse)) as UartMessageResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static UartMessageResponse create() => UartMessageResponse._();
  UartMessageResponse createEmptyInstance() => create();
  static $pb.PbList<UartMessageResponse> createRepeated() => $pb.PbList<UartMessageResponse>();
  @$core.pragma('dart2js:noInline')
  static UartMessageResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<UartMessageResponse>(create);
  static UartMessageResponse? _defaultInstance;

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

class DutEnablePowerRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutEnablePowerRequest', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'enable')
    ..hasRequiredFields = false
  ;

  DutEnablePowerRequest._() : super();
  factory DutEnablePowerRequest({
    $core.bool? enable,
  }) {
    final _result = create();
    if (enable != null) {
      _result.enable = enable;
    }
    return _result;
  }
  factory DutEnablePowerRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutEnablePowerRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutEnablePowerRequest clone() => DutEnablePowerRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutEnablePowerRequest copyWith(void Function(DutEnablePowerRequest) updates) => super.copyWith((message) => updates(message as DutEnablePowerRequest)) as DutEnablePowerRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutEnablePowerRequest create() => DutEnablePowerRequest._();
  DutEnablePowerRequest createEmptyInstance() => create();
  static $pb.PbList<DutEnablePowerRequest> createRepeated() => $pb.PbList<DutEnablePowerRequest>();
  @$core.pragma('dart2js:noInline')
  static DutEnablePowerRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutEnablePowerRequest>(create);
  static DutEnablePowerRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get enable => $_getBF(0);
  @$pb.TagNumber(1)
  set enable($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasEnable() => $_has(0);
  @$pb.TagNumber(1)
  void clearEnable() => clearField(1);
}

class DutEnablePowerResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutEnablePowerResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  DutEnablePowerResponse._() : super();
  factory DutEnablePowerResponse({
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
  factory DutEnablePowerResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutEnablePowerResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutEnablePowerResponse clone() => DutEnablePowerResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutEnablePowerResponse copyWith(void Function(DutEnablePowerResponse) updates) => super.copyWith((message) => updates(message as DutEnablePowerResponse)) as DutEnablePowerResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutEnablePowerResponse create() => DutEnablePowerResponse._();
  DutEnablePowerResponse createEmptyInstance() => create();
  static $pb.PbList<DutEnablePowerResponse> createRepeated() => $pb.PbList<DutEnablePowerResponse>();
  @$core.pragma('dart2js:noInline')
  static DutEnablePowerResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutEnablePowerResponse>(create);
  static DutEnablePowerResponse? _defaultInstance;

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

class DutEnableChargerRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutEnableChargerRequest', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'enable')
    ..hasRequiredFields = false
  ;

  DutEnableChargerRequest._() : super();
  factory DutEnableChargerRequest({
    $core.bool? enable,
  }) {
    final _result = create();
    if (enable != null) {
      _result.enable = enable;
    }
    return _result;
  }
  factory DutEnableChargerRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutEnableChargerRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutEnableChargerRequest clone() => DutEnableChargerRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutEnableChargerRequest copyWith(void Function(DutEnableChargerRequest) updates) => super.copyWith((message) => updates(message as DutEnableChargerRequest)) as DutEnableChargerRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutEnableChargerRequest create() => DutEnableChargerRequest._();
  DutEnableChargerRequest createEmptyInstance() => create();
  static $pb.PbList<DutEnableChargerRequest> createRepeated() => $pb.PbList<DutEnableChargerRequest>();
  @$core.pragma('dart2js:noInline')
  static DutEnableChargerRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutEnableChargerRequest>(create);
  static DutEnableChargerRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get enable => $_getBF(0);
  @$pb.TagNumber(1)
  set enable($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasEnable() => $_has(0);
  @$pb.TagNumber(1)
  void clearEnable() => clearField(1);
}

class DutEnableChargerResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutEnableChargerResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  DutEnableChargerResponse._() : super();
  factory DutEnableChargerResponse({
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
  factory DutEnableChargerResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutEnableChargerResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutEnableChargerResponse clone() => DutEnableChargerResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutEnableChargerResponse copyWith(void Function(DutEnableChargerResponse) updates) => super.copyWith((message) => updates(message as DutEnableChargerResponse)) as DutEnableChargerResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutEnableChargerResponse create() => DutEnableChargerResponse._();
  DutEnableChargerResponse createEmptyInstance() => create();
  static $pb.PbList<DutEnableChargerResponse> createRepeated() => $pb.PbList<DutEnableChargerResponse>();
  @$core.pragma('dart2js:noInline')
  static DutEnableChargerResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutEnableChargerResponse>(create);
  static DutEnableChargerResponse? _defaultInstance;

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

class DutSetOutputVoltageRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutSetOutputVoltageRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voltageMv', $pb.PbFieldType.OU3)
    ..hasRequiredFields = false
  ;

  DutSetOutputVoltageRequest._() : super();
  factory DutSetOutputVoltageRequest({
    $core.int? voltageMv,
  }) {
    final _result = create();
    if (voltageMv != null) {
      _result.voltageMv = voltageMv;
    }
    return _result;
  }
  factory DutSetOutputVoltageRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutSetOutputVoltageRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutSetOutputVoltageRequest clone() => DutSetOutputVoltageRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutSetOutputVoltageRequest copyWith(void Function(DutSetOutputVoltageRequest) updates) => super.copyWith((message) => updates(message as DutSetOutputVoltageRequest)) as DutSetOutputVoltageRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutSetOutputVoltageRequest create() => DutSetOutputVoltageRequest._();
  DutSetOutputVoltageRequest createEmptyInstance() => create();
  static $pb.PbList<DutSetOutputVoltageRequest> createRepeated() => $pb.PbList<DutSetOutputVoltageRequest>();
  @$core.pragma('dart2js:noInline')
  static DutSetOutputVoltageRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutSetOutputVoltageRequest>(create);
  static DutSetOutputVoltageRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get voltageMv => $_getIZ(0);
  @$pb.TagNumber(1)
  set voltageMv($core.int v) { $_setUnsignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasVoltageMv() => $_has(0);
  @$pb.TagNumber(1)
  void clearVoltageMv() => clearField(1);
}

class DutSetOutputVoltageResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'DutSetOutputVoltageResponse', createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'success')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'error')
    ..hasRequiredFields = false
  ;

  DutSetOutputVoltageResponse._() : super();
  factory DutSetOutputVoltageResponse({
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
  factory DutSetOutputVoltageResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DutSetOutputVoltageResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DutSetOutputVoltageResponse clone() => DutSetOutputVoltageResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DutSetOutputVoltageResponse copyWith(void Function(DutSetOutputVoltageResponse) updates) => super.copyWith((message) => updates(message as DutSetOutputVoltageResponse)) as DutSetOutputVoltageResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static DutSetOutputVoltageResponse create() => DutSetOutputVoltageResponse._();
  DutSetOutputVoltageResponse createEmptyInstance() => create();
  static $pb.PbList<DutSetOutputVoltageResponse> createRepeated() => $pb.PbList<DutSetOutputVoltageResponse>();
  @$core.pragma('dart2js:noInline')
  static DutSetOutputVoltageResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DutSetOutputVoltageResponse>(create);
  static DutSetOutputVoltageResponse? _defaultInstance;

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


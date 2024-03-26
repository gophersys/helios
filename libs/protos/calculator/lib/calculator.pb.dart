///
//  Generated code. Do not modify.
//  source: calculator.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:core' as $core;

import 'package:protobuf/protobuf.dart' as $pb;

class AddIntegersRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AddIntegersRequest', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'number1', $pb.PbFieldType.OU3)
    ..a<$core.int>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'number2', $pb.PbFieldType.OU3)
    ..hasRequiredFields = false
  ;

  AddIntegersRequest._() : super();
  factory AddIntegersRequest({
    $core.int? number1,
    $core.int? number2,
  }) {
    final _result = create();
    if (number1 != null) {
      _result.number1 = number1;
    }
    if (number2 != null) {
      _result.number2 = number2;
    }
    return _result;
  }
  factory AddIntegersRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AddIntegersRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AddIntegersRequest clone() => AddIntegersRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AddIntegersRequest copyWith(void Function(AddIntegersRequest) updates) => super.copyWith((message) => updates(message as AddIntegersRequest)) as AddIntegersRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AddIntegersRequest create() => AddIntegersRequest._();
  AddIntegersRequest createEmptyInstance() => create();
  static $pb.PbList<AddIntegersRequest> createRepeated() => $pb.PbList<AddIntegersRequest>();
  @$core.pragma('dart2js:noInline')
  static AddIntegersRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AddIntegersRequest>(create);
  static AddIntegersRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get number1 => $_getIZ(0);
  @$pb.TagNumber(1)
  set number1($core.int v) { $_setUnsignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasNumber1() => $_has(0);
  @$pb.TagNumber(1)
  void clearNumber1() => clearField(1);

  @$pb.TagNumber(2)
  $core.int get number2 => $_getIZ(1);
  @$pb.TagNumber(2)
  set number2($core.int v) { $_setUnsignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasNumber2() => $_has(1);
  @$pb.TagNumber(2)
  void clearNumber2() => clearField(2);
}

class AddIntegersResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AddIntegersResponse', createEmptyInstance: create)
    ..a<$core.int>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'result', $pb.PbFieldType.OU3)
    ..hasRequiredFields = false
  ;

  AddIntegersResponse._() : super();
  factory AddIntegersResponse({
    $core.int? result,
  }) {
    final _result = create();
    if (result != null) {
      _result.result = result;
    }
    return _result;
  }
  factory AddIntegersResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AddIntegersResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AddIntegersResponse clone() => AddIntegersResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AddIntegersResponse copyWith(void Function(AddIntegersResponse) updates) => super.copyWith((message) => updates(message as AddIntegersResponse)) as AddIntegersResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AddIntegersResponse create() => AddIntegersResponse._();
  AddIntegersResponse createEmptyInstance() => create();
  static $pb.PbList<AddIntegersResponse> createRepeated() => $pb.PbList<AddIntegersResponse>();
  @$core.pragma('dart2js:noInline')
  static AddIntegersResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AddIntegersResponse>(create);
  static AddIntegersResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get result => $_getIZ(0);
  @$pb.TagNumber(1)
  set result($core.int v) { $_setUnsignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasResult() => $_has(0);
  @$pb.TagNumber(1)
  void clearResult() => clearField(1);
}


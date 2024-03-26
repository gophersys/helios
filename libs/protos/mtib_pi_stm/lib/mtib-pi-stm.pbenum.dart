///
//  Generated code. Do not modify.
//  source: mtib-pi-stm.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

// ignore_for_file: UNDEFINED_SHOWN_NAME
import 'dart:core' as $core;
import 'package:protobuf/protobuf.dart' as $pb;

class GpioDirection extends $pb.ProtobufEnum {
  static const GpioDirection INPUT = GpioDirection._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'INPUT');
  static const GpioDirection OUTPUT = GpioDirection._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'OUTPUT');

  static const $core.List<GpioDirection> values = <GpioDirection> [
    INPUT,
    OUTPUT,
  ];

  static final $core.Map<$core.int, GpioDirection> _byValue = $pb.ProtobufEnum.initByValue(values);
  static GpioDirection? valueOf($core.int value) => _byValue[value];

  const GpioDirection._($core.int v, $core.String n) : super(v, n);
}

class GpioValue extends $pb.ProtobufEnum {
  static const GpioValue LOW = GpioValue._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'LOW');
  static const GpioValue HIGH = GpioValue._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'HIGH');

  static const $core.List<GpioValue> values = <GpioValue> [
    LOW,
    HIGH,
  ];

  static final $core.Map<$core.int, GpioValue> _byValue = $pb.ProtobufEnum.initByValue(values);
  static GpioValue? valueOf($core.int value) => _byValue[value];

  const GpioValue._($core.int v, $core.String n) : super(v, n);
}

class GpioConfigureResistorConfig extends $pb.ProtobufEnum {
  static const GpioConfigureResistorConfig RESISTOR_PULL_UP = GpioConfigureResistorConfig._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'RESISTOR_PULL_UP');
  static const GpioConfigureResistorConfig RESISTOR_PULL_DOWN = GpioConfigureResistorConfig._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'RESISTOR_PULL_DOWN');

  static const $core.List<GpioConfigureResistorConfig> values = <GpioConfigureResistorConfig> [
    RESISTOR_PULL_UP,
    RESISTOR_PULL_DOWN,
  ];

  static final $core.Map<$core.int, GpioConfigureResistorConfig> _byValue = $pb.ProtobufEnum.initByValue(values);
  static GpioConfigureResistorConfig? valueOf($core.int value) => _byValue[value];

  const GpioConfigureResistorConfig._($core.int v, $core.String n) : super(v, n);
}

class ChannelNumber extends $pb.ProtobufEnum {
  static const ChannelNumber CHANNEL_0 = ChannelNumber._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'CHANNEL_0');
  static const ChannelNumber CHANNEL_1 = ChannelNumber._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'CHANNEL_1');
  static const ChannelNumber CHANNEL_2 = ChannelNumber._(2, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'CHANNEL_2');
  static const ChannelNumber CHANNEL_3 = ChannelNumber._(3, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'CHANNEL_3');
  static const ChannelNumber CHANNEL_4 = ChannelNumber._(4, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'CHANNEL_4');
  static const ChannelNumber CHANNEL_5 = ChannelNumber._(5, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'CHANNEL_5');
  static const ChannelNumber CHANNEL_6 = ChannelNumber._(6, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'CHANNEL_6');
  static const ChannelNumber CHANNEL_7 = ChannelNumber._(7, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'CHANNEL_7');

  static const $core.List<ChannelNumber> values = <ChannelNumber> [
    CHANNEL_0,
    CHANNEL_1,
    CHANNEL_2,
    CHANNEL_3,
    CHANNEL_4,
    CHANNEL_5,
    CHANNEL_6,
    CHANNEL_7,
  ];

  static final $core.Map<$core.int, ChannelNumber> _byValue = $pb.ProtobufEnum.initByValue(values);
  static ChannelNumber? valueOf($core.int value) => _byValue[value];

  const ChannelNumber._($core.int v, $core.String n) : super(v, n);
}


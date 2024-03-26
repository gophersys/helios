///
//  Generated code. Do not modify.
//  source: mtib-cs-pi.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

// ignore_for_file: UNDEFINED_SHOWN_NAME
import 'dart:core' as $core;
import 'package:protobuf/protobuf.dart' as $pb;

class Gpio extends $pb.ProtobufEnum {
  static const Gpio GPIO_0 = Gpio._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_0');
  static const Gpio GPIO_1 = Gpio._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_1');
  static const Gpio GPIO_2 = Gpio._(2, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_2');
  static const Gpio GPIO_3 = Gpio._(3, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_3');
  static const Gpio GPIO_4 = Gpio._(4, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_4');
  static const Gpio GPIO_5 = Gpio._(5, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_5');
  static const Gpio GPIO_6 = Gpio._(6, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_6');

  static const $core.List<Gpio> values = <Gpio> [
    GPIO_0,
    GPIO_1,
    GPIO_2,
    GPIO_3,
    GPIO_4,
    GPIO_5,
    GPIO_6,
  ];

  static final $core.Map<$core.int, Gpio> _byValue = $pb.ProtobufEnum.initByValue(values);
  static Gpio? valueOf($core.int value) => _byValue[value];

  const Gpio._($core.int v, $core.String n) : super(v, n);
}

class GpioType extends $pb.ProtobufEnum {
  static const GpioType GPIO_INPUT = GpioType._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_INPUT');
  static const GpioType GPIO_OUTPUT = GpioType._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_OUTPUT');

  static const $core.List<GpioType> values = <GpioType> [
    GPIO_INPUT,
    GPIO_OUTPUT,
  ];

  static final $core.Map<$core.int, GpioType> _byValue = $pb.ProtobufEnum.initByValue(values);
  static GpioType? valueOf($core.int value) => _byValue[value];

  const GpioType._($core.int v, $core.String n) : super(v, n);
}

class GpioResistorConfig extends $pb.ProtobufEnum {
  static const GpioResistorConfig GPIO_RESISTOR_PULL_UP = GpioResistorConfig._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_RESISTOR_PULL_UP');
  static const GpioResistorConfig GPIO_RESISTOR_PULL_DOWN = GpioResistorConfig._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'GPIO_RESISTOR_PULL_DOWN');

  static const $core.List<GpioResistorConfig> values = <GpioResistorConfig> [
    GPIO_RESISTOR_PULL_UP,
    GPIO_RESISTOR_PULL_DOWN,
  ];

  static final $core.Map<$core.int, GpioResistorConfig> _byValue = $pb.ProtobufEnum.initByValue(values);
  static GpioResistorConfig? valueOf($core.int value) => _byValue[value];

  const GpioResistorConfig._($core.int v, $core.String n) : super(v, n);
}

class AdcChannel extends $pb.ProtobufEnum {
  static const AdcChannel ADC_CHANNEL_0 = AdcChannel._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'ADC_CHANNEL_0');
  static const AdcChannel ADC_CHANNEL_1 = AdcChannel._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'ADC_CHANNEL_1');
  static const AdcChannel ADC_CHANNEL_2 = AdcChannel._(2, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'ADC_CHANNEL_2');
  static const AdcChannel ADC_CHANNEL_3 = AdcChannel._(3, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'ADC_CHANNEL_3');
  static const AdcChannel ADC_CHANNEL_4 = AdcChannel._(4, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'ADC_CHANNEL_4');
  static const AdcChannel ADC_CHANNEL_5 = AdcChannel._(5, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'ADC_CHANNEL_5');
  static const AdcChannel ADC_CHANNEL_6 = AdcChannel._(6, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'ADC_CHANNEL_6');
  static const AdcChannel ADC_CHANNEL_7 = AdcChannel._(7, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'ADC_CHANNEL_7');

  static const $core.List<AdcChannel> values = <AdcChannel> [
    ADC_CHANNEL_0,
    ADC_CHANNEL_1,
    ADC_CHANNEL_2,
    ADC_CHANNEL_3,
    ADC_CHANNEL_4,
    ADC_CHANNEL_5,
    ADC_CHANNEL_6,
    ADC_CHANNEL_7,
  ];

  static final $core.Map<$core.int, AdcChannel> _byValue = $pb.ProtobufEnum.initByValue(values);
  static AdcChannel? valueOf($core.int value) => _byValue[value];

  const AdcChannel._($core.int v, $core.String n) : super(v, n);
}

class UartPort extends $pb.ProtobufEnum {
  static const UartPort UART_PORT_0 = UartPort._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'UART_PORT_0');
  static const UartPort UART_PORT_1 = UartPort._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'UART_PORT_1');

  static const $core.List<UartPort> values = <UartPort> [
    UART_PORT_0,
    UART_PORT_1,
  ];

  static final $core.Map<$core.int, UartPort> _byValue = $pb.ProtobufEnum.initByValue(values);
  static UartPort? valueOf($core.int value) => _byValue[value];

  const UartPort._($core.int v, $core.String n) : super(v, n);
}

class UartBaudRate extends $pb.ProtobufEnum {
  static const UartBaudRate UART_BAUDRATE_9600 = UartBaudRate._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'UART_BAUDRATE_9600');
  static const UartBaudRate UART_BAUDRATE_115200 = UartBaudRate._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'UART_BAUDRATE_115200');
  static const UartBaudRate UART_BAUDRATE_576000 = UartBaudRate._(2, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'UART_BAUDRATE_576000');
  static const UartBaudRate UART_BAUDRATE_921600 = UartBaudRate._(3, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'UART_BAUDRATE_921600');

  static const $core.List<UartBaudRate> values = <UartBaudRate> [
    UART_BAUDRATE_9600,
    UART_BAUDRATE_115200,
    UART_BAUDRATE_576000,
    UART_BAUDRATE_921600,
  ];

  static final $core.Map<$core.int, UartBaudRate> _byValue = $pb.ProtobufEnum.initByValue(values);
  static UartBaudRate? valueOf($core.int value) => _byValue[value];

  const UartBaudRate._($core.int v, $core.String n) : super(v, n);
}

class DeviceType extends $pb.ProtobufEnum {
  static const DeviceType DEVICE_NRF9160 = DeviceType._(0, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'DEVICE_NRF9160');
  static const DeviceType DEVICE_NRF82840 = DeviceType._(1, const $core.bool.fromEnvironment('protobuf.omit_enum_names') ? '' : 'DEVICE_NRF82840');

  static const $core.List<DeviceType> values = <DeviceType> [
    DEVICE_NRF9160,
    DEVICE_NRF82840,
  ];

  static final $core.Map<$core.int, DeviceType> _byValue = $pb.ProtobufEnum.initByValue(values);
  static DeviceType? valueOf($core.int value) => _byValue[value];

  const DeviceType._($core.int v, $core.String n) : super(v, n);
}


///
//  Generated code. Do not modify.
//  source: mtib-pi-stm.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,deprecated_member_use_from_same_package,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:core' as $core;
import 'dart:convert' as $convert;
import 'dart:typed_data' as $typed_data;
@$core.Deprecated('Use gpioDirectionDescriptor instead')
const GpioDirection$json = const {
  '1': 'GpioDirection',
  '2': const [
    const {'1': 'INPUT', '2': 0},
    const {'1': 'OUTPUT', '2': 1},
  ],
};

/// Descriptor for `GpioDirection`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List gpioDirectionDescriptor = $convert.base64Decode('Cg1HcGlvRGlyZWN0aW9uEgkKBUlOUFVUEAASCgoGT1VUUFVUEAE=');
@$core.Deprecated('Use gpioValueDescriptor instead')
const GpioValue$json = const {
  '1': 'GpioValue',
  '2': const [
    const {'1': 'LOW', '2': 0},
    const {'1': 'HIGH', '2': 1},
  ],
};

/// Descriptor for `GpioValue`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List gpioValueDescriptor = $convert.base64Decode('CglHcGlvVmFsdWUSBwoDTE9XEAASCAoESElHSBAB');
@$core.Deprecated('Use gpioConfigureResistorConfigDescriptor instead')
const GpioConfigureResistorConfig$json = const {
  '1': 'GpioConfigureResistorConfig',
  '2': const [
    const {'1': 'RESISTOR_PULL_UP', '2': 0},
    const {'1': 'RESISTOR_PULL_DOWN', '2': 1},
  ],
};

/// Descriptor for `GpioConfigureResistorConfig`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List gpioConfigureResistorConfigDescriptor = $convert.base64Decode('ChtHcGlvQ29uZmlndXJlUmVzaXN0b3JDb25maWcSFAoQUkVTSVNUT1JfUFVMTF9VUBAAEhYKElJFU0lTVE9SX1BVTExfRE9XThAB');
@$core.Deprecated('Use channelNumberDescriptor instead')
const ChannelNumber$json = const {
  '1': 'ChannelNumber',
  '2': const [
    const {'1': 'CHANNEL_0', '2': 0},
    const {'1': 'CHANNEL_1', '2': 1},
    const {'1': 'CHANNEL_2', '2': 2},
    const {'1': 'CHANNEL_3', '2': 3},
    const {'1': 'CHANNEL_4', '2': 4},
    const {'1': 'CHANNEL_5', '2': 5},
    const {'1': 'CHANNEL_6', '2': 6},
    const {'1': 'CHANNEL_7', '2': 7},
  ],
};

/// Descriptor for `ChannelNumber`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List channelNumberDescriptor = $convert.base64Decode('Cg1DaGFubmVsTnVtYmVyEg0KCUNIQU5ORUxfMBAAEg0KCUNIQU5ORUxfMRABEg0KCUNIQU5ORUxfMhACEg0KCUNIQU5ORUxfMxADEg0KCUNIQU5ORUxfNBAEEg0KCUNIQU5ORUxfNRAFEg0KCUNIQU5ORUxfNhAGEg0KCUNIQU5ORUxfNxAH');
@$core.Deprecated('Use gpioConfigurePinRequestDescriptor instead')
const GpioConfigurePinRequest$json = const {
  '1': 'GpioConfigurePinRequest',
  '2': const [
    const {'1': 'pin_number', '3': 1, '4': 1, '5': 5, '10': 'pinNumber'},
    const {'1': 'direction', '3': 2, '4': 1, '5': 14, '6': '.GpioDirection', '10': 'direction'},
    const {'1': 'resistor', '3': 3, '4': 1, '5': 14, '6': '.GpioConfigureResistorConfig', '10': 'resistor'},
  ],
};

/// Descriptor for `GpioConfigurePinRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioConfigurePinRequestDescriptor = $convert.base64Decode('ChdHcGlvQ29uZmlndXJlUGluUmVxdWVzdBIdCgpwaW5fbnVtYmVyGAEgASgFUglwaW5OdW1iZXISLAoJZGlyZWN0aW9uGAIgASgOMg4uR3Bpb0RpcmVjdGlvblIJZGlyZWN0aW9uEjgKCHJlc2lzdG9yGAMgASgOMhwuR3Bpb0NvbmZpZ3VyZVJlc2lzdG9yQ29uZmlnUghyZXNpc3Rvcg==');
@$core.Deprecated('Use gpioConfigurePinResponseDescriptor instead')
const GpioConfigurePinResponse$json = const {
  '1': 'GpioConfigurePinResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `GpioConfigurePinResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioConfigurePinResponseDescriptor = $convert.base64Decode('ChhHcGlvQ29uZmlndXJlUGluUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3I=');
@$core.Deprecated('Use gpioSetPinRequestDescriptor instead')
const GpioSetPinRequest$json = const {
  '1': 'GpioSetPinRequest',
  '2': const [
    const {'1': 'pin_number', '3': 1, '4': 1, '5': 5, '10': 'pinNumber'},
    const {'1': 'value', '3': 2, '4': 1, '5': 14, '6': '.GpioValue', '10': 'value'},
  ],
};

/// Descriptor for `GpioSetPinRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioSetPinRequestDescriptor = $convert.base64Decode('ChFHcGlvU2V0UGluUmVxdWVzdBIdCgpwaW5fbnVtYmVyGAEgASgFUglwaW5OdW1iZXISIAoFdmFsdWUYAiABKA4yCi5HcGlvVmFsdWVSBXZhbHVl');
@$core.Deprecated('Use gpioSetPinResponseDescriptor instead')
const GpioSetPinResponse$json = const {
  '1': 'GpioSetPinResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `GpioSetPinResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioSetPinResponseDescriptor = $convert.base64Decode('ChJHcGlvU2V0UGluUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3I=');
@$core.Deprecated('Use gpioReadPinRequestDescriptor instead')
const GpioReadPinRequest$json = const {
  '1': 'GpioReadPinRequest',
  '2': const [
    const {'1': 'pin_number', '3': 1, '4': 1, '5': 5, '10': 'pinNumber'},
  ],
};

/// Descriptor for `GpioReadPinRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioReadPinRequestDescriptor = $convert.base64Decode('ChJHcGlvUmVhZFBpblJlcXVlc3QSHQoKcGluX251bWJlchgBIAEoBVIJcGluTnVtYmVy');
@$core.Deprecated('Use gpioReadPinResponseDescriptor instead')
const GpioReadPinResponse$json = const {
  '1': 'GpioReadPinResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'value', '3': 3, '4': 1, '5': 14, '6': '.GpioValue', '10': 'value'},
  ],
};

/// Descriptor for `GpioReadPinResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioReadPinResponseDescriptor = $convert.base64Decode('ChNHcGlvUmVhZFBpblJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEiAKBXZhbHVlGAMgASgOMgouR3Bpb1ZhbHVlUgV2YWx1ZQ==');
@$core.Deprecated('Use adcReadChannelRequestDescriptor instead')
const AdcReadChannelRequest$json = const {
  '1': 'AdcReadChannelRequest',
  '2': const [
    const {'1': 'channel_number', '3': 1, '4': 1, '5': 14, '6': '.ChannelNumber', '10': 'channelNumber'},
    const {'1': 'delay_ms', '3': 2, '4': 1, '5': 5, '10': 'delayMs'},
  ],
};

/// Descriptor for `AdcReadChannelRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List adcReadChannelRequestDescriptor = $convert.base64Decode('ChVBZGNSZWFkQ2hhbm5lbFJlcXVlc3QSNQoOY2hhbm5lbF9udW1iZXIYASABKA4yDi5DaGFubmVsTnVtYmVyUg1jaGFubmVsTnVtYmVyEhkKCGRlbGF5X21zGAIgASgFUgdkZWxheU1z');
@$core.Deprecated('Use adcReadChannelResponseDescriptor instead')
const AdcReadChannelResponse$json = const {
  '1': 'AdcReadChannelResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'voltage', '3': 3, '4': 1, '5': 1, '10': 'voltage'},
  ],
};

/// Descriptor for `AdcReadChannelResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List adcReadChannelResponseDescriptor = $convert.base64Decode('ChZBZGNSZWFkQ2hhbm5lbFJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEhgKB3ZvbHRhZ2UYAyABKAFSB3ZvbHRhZ2U=');
@$core.Deprecated('Use adcReadAllChannelsRequestDescriptor instead')
const AdcReadAllChannelsRequest$json = const {
  '1': 'AdcReadAllChannelsRequest',
  '2': const [
    const {'1': 'delay_ms', '3': 1, '4': 1, '5': 5, '10': 'delayMs'},
  ],
};

/// Descriptor for `AdcReadAllChannelsRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List adcReadAllChannelsRequestDescriptor = $convert.base64Decode('ChlBZGNSZWFkQWxsQ2hhbm5lbHNSZXF1ZXN0EhkKCGRlbGF5X21zGAEgASgFUgdkZWxheU1z');
@$core.Deprecated('Use adcReadAllChannelsResponseDescriptor instead')
const AdcReadAllChannelsResponse$json = const {
  '1': 'AdcReadAllChannelsResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'voltage', '3': 3, '4': 3, '5': 1, '10': 'voltage'},
  ],
};

/// Descriptor for `AdcReadAllChannelsResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List adcReadAllChannelsResponseDescriptor = $convert.base64Decode('ChpBZGNSZWFkQWxsQ2hhbm5lbHNSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvchIYCgd2b2x0YWdlGAMgAygBUgd2b2x0YWdl');
@$core.Deprecated('Use bmp390ReadValuesRequestDescriptor instead')
const Bmp390ReadValuesRequest$json = const {
  '1': 'Bmp390ReadValuesRequest',
};

/// Descriptor for `Bmp390ReadValuesRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List bmp390ReadValuesRequestDescriptor = $convert.base64Decode('ChdCbXAzOTBSZWFkVmFsdWVzUmVxdWVzdA==');
@$core.Deprecated('Use bmp390ReadValuesResponseDescriptor instead')
const Bmp390ReadValuesResponse$json = const {
  '1': 'Bmp390ReadValuesResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'temperature_f', '3': 3, '4': 1, '5': 1, '10': 'temperatureF'},
    const {'1': 'pressure_hg', '3': 4, '4': 1, '5': 1, '10': 'pressureHg'},
    const {'1': 'altitude_ft', '3': 5, '4': 1, '5': 1, '10': 'altitudeFt'},
  ],
};

/// Descriptor for `Bmp390ReadValuesResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List bmp390ReadValuesResponseDescriptor = $convert.base64Decode('ChhCbXAzOTBSZWFkVmFsdWVzUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3ISIwoNdGVtcGVyYXR1cmVfZhgDIAEoAVIMdGVtcGVyYXR1cmVGEh8KC3ByZXNzdXJlX2hnGAQgASgBUgpwcmVzc3VyZUhnEh8KC2FsdGl0dWRlX2Z0GAUgASgBUgphbHRpdHVkZUZ0');
@$core.Deprecated('Use lis2de12ReadValuesRequestDescriptor instead')
const Lis2de12ReadValuesRequest$json = const {
  '1': 'Lis2de12ReadValuesRequest',
};

/// Descriptor for `Lis2de12ReadValuesRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List lis2de12ReadValuesRequestDescriptor = $convert.base64Decode('ChlMaXMyZGUxMlJlYWRWYWx1ZXNSZXF1ZXN0');
@$core.Deprecated('Use lis2de12ReadValuesResponseDescriptor instead')
const Lis2de12ReadValuesResponse$json = const {
  '1': 'Lis2de12ReadValuesResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'x_value', '3': 3, '4': 1, '5': 1, '10': 'xValue'},
    const {'1': 'y_value', '3': 4, '4': 1, '5': 1, '10': 'yValue'},
    const {'1': 'z_value', '3': 5, '4': 1, '5': 1, '10': 'zValue'},
  ],
};

/// Descriptor for `Lis2de12ReadValuesResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List lis2de12ReadValuesResponseDescriptor = $convert.base64Decode('ChpMaXMyZGUxMlJlYWRWYWx1ZXNSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvchIXCgd4X3ZhbHVlGAMgASgBUgZ4VmFsdWUSFwoHeV92YWx1ZRgEIAEoAVIGeVZhbHVlEhcKB3pfdmFsdWUYBSABKAFSBnpWYWx1ZQ==');
@$core.Deprecated('Use lis2de12ReadMaxForceRequestDescriptor instead')
const Lis2de12ReadMaxForceRequest$json = const {
  '1': 'Lis2de12ReadMaxForceRequest',
};

/// Descriptor for `Lis2de12ReadMaxForceRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List lis2de12ReadMaxForceRequestDescriptor = $convert.base64Decode('ChtMaXMyZGUxMlJlYWRNYXhGb3JjZVJlcXVlc3Q=');
@$core.Deprecated('Use lis2de12ReadMaxForceResponseDescriptor instead')
const Lis2de12ReadMaxForceResponse$json = const {
  '1': 'Lis2de12ReadMaxForceResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'max_force', '3': 3, '4': 1, '5': 1, '10': 'maxForce'},
  ],
};

/// Descriptor for `Lis2de12ReadMaxForceResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List lis2de12ReadMaxForceResponseDescriptor = $convert.base64Decode('ChxMaXMyZGUxMlJlYWRNYXhGb3JjZVJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEhsKCW1heF9mb3JjZRgDIAEoAVIIbWF4Rm9yY2U=');
@$core.Deprecated('Use eepromWriteToMemRequestDescriptor instead')
const EepromWriteToMemRequest$json = const {
  '1': 'EepromWriteToMemRequest',
  '2': const [
    const {'1': 'address', '3': 1, '4': 1, '5': 5, '10': 'address'},
    const {'1': 'data', '3': 2, '4': 1, '5': 12, '10': 'data'},
    const {'1': 'len', '3': 3, '4': 1, '5': 5, '10': 'len'},
  ],
};

/// Descriptor for `EepromWriteToMemRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List eepromWriteToMemRequestDescriptor = $convert.base64Decode('ChdFZXByb21Xcml0ZVRvTWVtUmVxdWVzdBIYCgdhZGRyZXNzGAEgASgFUgdhZGRyZXNzEhIKBGRhdGEYAiABKAxSBGRhdGESEAoDbGVuGAMgASgFUgNsZW4=');
@$core.Deprecated('Use eepromWriteToMemResponseDescriptor instead')
const EepromWriteToMemResponse$json = const {
  '1': 'EepromWriteToMemResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `EepromWriteToMemResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List eepromWriteToMemResponseDescriptor = $convert.base64Decode('ChhFZXByb21Xcml0ZVRvTWVtUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3I=');
@$core.Deprecated('Use eepromReadFromMemRequestDescriptor instead')
const EepromReadFromMemRequest$json = const {
  '1': 'EepromReadFromMemRequest',
  '2': const [
    const {'1': 'address', '3': 1, '4': 1, '5': 5, '10': 'address'},
    const {'1': 'len', '3': 2, '4': 1, '5': 5, '10': 'len'},
  ],
};

/// Descriptor for `EepromReadFromMemRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List eepromReadFromMemRequestDescriptor = $convert.base64Decode('ChhFZXByb21SZWFkRnJvbU1lbVJlcXVlc3QSGAoHYWRkcmVzcxgBIAEoBVIHYWRkcmVzcxIQCgNsZW4YAiABKAVSA2xlbg==');
@$core.Deprecated('Use eepromReadFromMemResponseDescriptor instead')
const EepromReadFromMemResponse$json = const {
  '1': 'EepromReadFromMemResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'data', '3': 3, '4': 1, '5': 12, '10': 'data'},
  ],
};

/// Descriptor for `EepromReadFromMemResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List eepromReadFromMemResponseDescriptor = $convert.base64Decode('ChlFZXByb21SZWFkRnJvbU1lbVJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEhIKBGRhdGEYAyABKAxSBGRhdGE=');
@$core.Deprecated('Use ina219ReadCurrentRequestDescriptor instead')
const Ina219ReadCurrentRequest$json = const {
  '1': 'Ina219ReadCurrentRequest',
};

/// Descriptor for `Ina219ReadCurrentRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List ina219ReadCurrentRequestDescriptor = $convert.base64Decode('ChhJbmEyMTlSZWFkQ3VycmVudFJlcXVlc3Q=');
@$core.Deprecated('Use ina219ReadCurrentResponseDescriptor instead')
const Ina219ReadCurrentResponse$json = const {
  '1': 'Ina219ReadCurrentResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'current_value_ma', '3': 3, '4': 1, '5': 5, '10': 'currentValueMa'},
  ],
};

/// Descriptor for `Ina219ReadCurrentResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List ina219ReadCurrentResponseDescriptor = $convert.base64Decode('ChlJbmEyMTlSZWFkQ3VycmVudFJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEigKEGN1cnJlbnRfdmFsdWVfbWEYAyABKAVSDmN1cnJlbnRWYWx1ZU1h');
@$core.Deprecated('Use ina219ReadVoltageRequestDescriptor instead')
const Ina219ReadVoltageRequest$json = const {
  '1': 'Ina219ReadVoltageRequest',
};

/// Descriptor for `Ina219ReadVoltageRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List ina219ReadVoltageRequestDescriptor = $convert.base64Decode('ChhJbmEyMTlSZWFkVm9sdGFnZVJlcXVlc3Q=');
@$core.Deprecated('Use ina219ReadVoltageResponseDescriptor instead')
const Ina219ReadVoltageResponse$json = const {
  '1': 'Ina219ReadVoltageResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'voltage_value_mv', '3': 3, '4': 1, '5': 13, '10': 'voltageValueMv'},
  ],
};

/// Descriptor for `Ina219ReadVoltageResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List ina219ReadVoltageResponseDescriptor = $convert.base64Decode('ChlJbmEyMTlSZWFkVm9sdGFnZVJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEigKEHZvbHRhZ2VfdmFsdWVfbXYYAyABKA1SDnZvbHRhZ2VWYWx1ZU12');
@$core.Deprecated('Use ina219ReadPowerRequestDescriptor instead')
const Ina219ReadPowerRequest$json = const {
  '1': 'Ina219ReadPowerRequest',
};

/// Descriptor for `Ina219ReadPowerRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List ina219ReadPowerRequestDescriptor = $convert.base64Decode('ChZJbmEyMTlSZWFkUG93ZXJSZXF1ZXN0');
@$core.Deprecated('Use ina219ReadPowerResponseDescriptor instead')
const Ina219ReadPowerResponse$json = const {
  '1': 'Ina219ReadPowerResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'power_value_mw', '3': 3, '4': 1, '5': 5, '10': 'powerValueMw'},
  ],
};

/// Descriptor for `Ina219ReadPowerResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List ina219ReadPowerResponseDescriptor = $convert.base64Decode('ChdJbmEyMTlSZWFkUG93ZXJSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvchIkCg5wb3dlcl92YWx1ZV9tdxgDIAEoBVIMcG93ZXJWYWx1ZU13');
@$core.Deprecated('Use uartMessageRequestDescriptor instead')
const UartMessageRequest$json = const {
  '1': 'UartMessageRequest',
  '2': const [
    const {'1': 'uart_port', '3': 1, '4': 1, '5': 13, '10': 'uartPort'},
    const {'1': 'data', '3': 2, '4': 1, '5': 12, '10': 'data'},
  ],
};

/// Descriptor for `UartMessageRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List uartMessageRequestDescriptor = $convert.base64Decode('ChJVYXJ0TWVzc2FnZVJlcXVlc3QSGwoJdWFydF9wb3J0GAEgASgNUgh1YXJ0UG9ydBISCgRkYXRhGAIgASgMUgRkYXRh');
@$core.Deprecated('Use uartMessageResponseDescriptor instead')
const UartMessageResponse$json = const {
  '1': 'UartMessageResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `UartMessageResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List uartMessageResponseDescriptor = $convert.base64Decode('ChNVYXJ0TWVzc2FnZVJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9y');
@$core.Deprecated('Use dutEnablePowerRequestDescriptor instead')
const DutEnablePowerRequest$json = const {
  '1': 'DutEnablePowerRequest',
  '2': const [
    const {'1': 'enable', '3': 1, '4': 1, '5': 8, '10': 'enable'},
  ],
};

/// Descriptor for `DutEnablePowerRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutEnablePowerRequestDescriptor = $convert.base64Decode('ChVEdXRFbmFibGVQb3dlclJlcXVlc3QSFgoGZW5hYmxlGAEgASgIUgZlbmFibGU=');
@$core.Deprecated('Use dutEnablePowerResponseDescriptor instead')
const DutEnablePowerResponse$json = const {
  '1': 'DutEnablePowerResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `DutEnablePowerResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutEnablePowerResponseDescriptor = $convert.base64Decode('ChZEdXRFbmFibGVQb3dlclJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9y');
@$core.Deprecated('Use dutEnableChargerRequestDescriptor instead')
const DutEnableChargerRequest$json = const {
  '1': 'DutEnableChargerRequest',
  '2': const [
    const {'1': 'enable', '3': 1, '4': 1, '5': 8, '10': 'enable'},
  ],
};

/// Descriptor for `DutEnableChargerRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutEnableChargerRequestDescriptor = $convert.base64Decode('ChdEdXRFbmFibGVDaGFyZ2VyUmVxdWVzdBIWCgZlbmFibGUYASABKAhSBmVuYWJsZQ==');
@$core.Deprecated('Use dutEnableChargerResponseDescriptor instead')
const DutEnableChargerResponse$json = const {
  '1': 'DutEnableChargerResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `DutEnableChargerResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutEnableChargerResponseDescriptor = $convert.base64Decode('ChhEdXRFbmFibGVDaGFyZ2VyUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3I=');
@$core.Deprecated('Use dutSetOutputVoltageRequestDescriptor instead')
const DutSetOutputVoltageRequest$json = const {
  '1': 'DutSetOutputVoltageRequest',
  '2': const [
    const {'1': 'voltage_mv', '3': 1, '4': 1, '5': 13, '10': 'voltageMv'},
  ],
};

/// Descriptor for `DutSetOutputVoltageRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutSetOutputVoltageRequestDescriptor = $convert.base64Decode('ChpEdXRTZXRPdXRwdXRWb2x0YWdlUmVxdWVzdBIdCgp2b2x0YWdlX212GAEgASgNUgl2b2x0YWdlTXY=');
@$core.Deprecated('Use dutSetOutputVoltageResponseDescriptor instead')
const DutSetOutputVoltageResponse$json = const {
  '1': 'DutSetOutputVoltageResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `DutSetOutputVoltageResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutSetOutputVoltageResponseDescriptor = $convert.base64Decode('ChtEdXRTZXRPdXRwdXRWb2x0YWdlUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3I=');

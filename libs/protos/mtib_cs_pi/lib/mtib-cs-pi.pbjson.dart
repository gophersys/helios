///
//  Generated code. Do not modify.
//  source: mtib-cs-pi.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,deprecated_member_use_from_same_package,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:core' as $core;
import 'dart:convert' as $convert;
import 'dart:typed_data' as $typed_data;
@$core.Deprecated('Use gpioDescriptor instead')
const Gpio$json = const {
  '1': 'Gpio',
  '2': const [
    const {'1': 'GPIO_0', '2': 0},
    const {'1': 'GPIO_1', '2': 1},
    const {'1': 'GPIO_2', '2': 2},
    const {'1': 'GPIO_3', '2': 3},
    const {'1': 'GPIO_4', '2': 4},
    const {'1': 'GPIO_5', '2': 5},
    const {'1': 'GPIO_6', '2': 6},
  ],
};

/// Descriptor for `Gpio`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List gpioDescriptor = $convert.base64Decode('CgRHcGlvEgoKBkdQSU9fMBAAEgoKBkdQSU9fMRABEgoKBkdQSU9fMhACEgoKBkdQSU9fMxADEgoKBkdQSU9fNBAEEgoKBkdQSU9fNRAFEgoKBkdQSU9fNhAG');
@$core.Deprecated('Use gpioTypeDescriptor instead')
const GpioType$json = const {
  '1': 'GpioType',
  '2': const [
    const {'1': 'GPIO_INPUT', '2': 0},
    const {'1': 'GPIO_OUTPUT', '2': 1},
  ],
};

/// Descriptor for `GpioType`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List gpioTypeDescriptor = $convert.base64Decode('CghHcGlvVHlwZRIOCgpHUElPX0lOUFVUEAASDwoLR1BJT19PVVRQVVQQAQ==');
@$core.Deprecated('Use gpioResistorConfigDescriptor instead')
const GpioResistorConfig$json = const {
  '1': 'GpioResistorConfig',
  '2': const [
    const {'1': 'GPIO_RESISTOR_PULL_UP', '2': 0},
    const {'1': 'GPIO_RESISTOR_PULL_DOWN', '2': 1},
  ],
};

/// Descriptor for `GpioResistorConfig`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List gpioResistorConfigDescriptor = $convert.base64Decode('ChJHcGlvUmVzaXN0b3JDb25maWcSGQoVR1BJT19SRVNJU1RPUl9QVUxMX1VQEAASGwoXR1BJT19SRVNJU1RPUl9QVUxMX0RPV04QAQ==');
@$core.Deprecated('Use adcChannelDescriptor instead')
const AdcChannel$json = const {
  '1': 'AdcChannel',
  '2': const [
    const {'1': 'ADC_CHANNEL_0', '2': 0},
    const {'1': 'ADC_CHANNEL_1', '2': 1},
    const {'1': 'ADC_CHANNEL_2', '2': 2},
    const {'1': 'ADC_CHANNEL_3', '2': 3},
    const {'1': 'ADC_CHANNEL_4', '2': 4},
    const {'1': 'ADC_CHANNEL_5', '2': 5},
    const {'1': 'ADC_CHANNEL_6', '2': 6},
    const {'1': 'ADC_CHANNEL_7', '2': 7},
  ],
};

/// Descriptor for `AdcChannel`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List adcChannelDescriptor = $convert.base64Decode('CgpBZGNDaGFubmVsEhEKDUFEQ19DSEFOTkVMXzAQABIRCg1BRENfQ0hBTk5FTF8xEAESEQoNQURDX0NIQU5ORUxfMhACEhEKDUFEQ19DSEFOTkVMXzMQAxIRCg1BRENfQ0hBTk5FTF80EAQSEQoNQURDX0NIQU5ORUxfNRAFEhEKDUFEQ19DSEFOTkVMXzYQBhIRCg1BRENfQ0hBTk5FTF83EAc=');
@$core.Deprecated('Use uartPortDescriptor instead')
const UartPort$json = const {
  '1': 'UartPort',
  '2': const [
    const {'1': 'UART_PORT_0', '2': 0},
    const {'1': 'UART_PORT_1', '2': 1},
  ],
};

/// Descriptor for `UartPort`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List uartPortDescriptor = $convert.base64Decode('CghVYXJ0UG9ydBIPCgtVQVJUX1BPUlRfMBAAEg8KC1VBUlRfUE9SVF8xEAE=');
@$core.Deprecated('Use uartBaudRateDescriptor instead')
const UartBaudRate$json = const {
  '1': 'UartBaudRate',
  '2': const [
    const {'1': 'UART_BAUDRATE_9600', '2': 0},
    const {'1': 'UART_BAUDRATE_115200', '2': 1},
    const {'1': 'UART_BAUDRATE_576000', '2': 2},
    const {'1': 'UART_BAUDRATE_921600', '2': 3},
  ],
};

/// Descriptor for `UartBaudRate`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List uartBaudRateDescriptor = $convert.base64Decode('CgxVYXJ0QmF1ZFJhdGUSFgoSVUFSVF9CQVVEUkFURV85NjAwEAASGAoUVUFSVF9CQVVEUkFURV8xMTUyMDAQARIYChRVQVJUX0JBVURSQVRFXzU3NjAwMBACEhgKFFVBUlRfQkFVRFJBVEVfOTIxNjAwEAM=');
@$core.Deprecated('Use deviceTypeDescriptor instead')
const DeviceType$json = const {
  '1': 'DeviceType',
  '2': const [
    const {'1': 'DEVICE_NRF9160', '2': 0},
    const {'1': 'DEVICE_NRF82840', '2': 1},
  ],
};

/// Descriptor for `DeviceType`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List deviceTypeDescriptor = $convert.base64Decode('CgpEZXZpY2VUeXBlEhIKDkRFVklDRV9OUkY5MTYwEAASEwoPREVWSUNFX05SRjgyODQwEAE=');
@$core.Deprecated('Use healthCheckRequestDescriptor instead')
const HealthCheckRequest$json = const {
  '1': 'HealthCheckRequest',
};

/// Descriptor for `HealthCheckRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List healthCheckRequestDescriptor = $convert.base64Decode('ChJIZWFsdGhDaGVja1JlcXVlc3Q=');
@$core.Deprecated('Use healthCheckResponseDescriptor instead')
const HealthCheckResponse$json = const {
  '1': 'HealthCheckResponse',
  '2': const [
    const {'1': 'ok', '3': 1, '4': 1, '5': 8, '10': 'ok'},
  ],
};

/// Descriptor for `HealthCheckResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List healthCheckResponseDescriptor = $convert.base64Decode('ChNIZWFsdGhDaGVja1Jlc3BvbnNlEg4KAm9rGAEgASgIUgJvaw==');
@$core.Deprecated('Use gpioConfigRequestDescriptor instead')
const GpioConfigRequest$json = const {
  '1': 'GpioConfigRequest',
  '2': const [
    const {'1': 'gpio', '3': 1, '4': 1, '5': 14, '6': '.Gpio', '10': 'gpio'},
    const {'1': 'type', '3': 2, '4': 1, '5': 14, '6': '.GpioType', '10': 'type'},
    const {'1': 'resistor', '3': 3, '4': 1, '5': 14, '6': '.GpioResistorConfig', '10': 'resistor'},
  ],
};

/// Descriptor for `GpioConfigRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioConfigRequestDescriptor = $convert.base64Decode('ChFHcGlvQ29uZmlnUmVxdWVzdBIZCgRncGlvGAEgASgOMgUuR3Bpb1IEZ3BpbxIdCgR0eXBlGAIgASgOMgkuR3Bpb1R5cGVSBHR5cGUSLwoIcmVzaXN0b3IYAyABKA4yEy5HcGlvUmVzaXN0b3JDb25maWdSCHJlc2lzdG9y');
@$core.Deprecated('Use gpioConfigResponseDescriptor instead')
const GpioConfigResponse$json = const {
  '1': 'GpioConfigResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `GpioConfigResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioConfigResponseDescriptor = $convert.base64Decode('ChJHcGlvQ29uZmlnUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3I=');
@$core.Deprecated('Use gpioWriteRequestDescriptor instead')
const GpioWriteRequest$json = const {
  '1': 'GpioWriteRequest',
  '2': const [
    const {'1': 'gpio', '3': 1, '4': 1, '5': 14, '6': '.Gpio', '10': 'gpio'},
    const {'1': 'state', '3': 2, '4': 1, '5': 8, '10': 'state'},
  ],
};

/// Descriptor for `GpioWriteRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioWriteRequestDescriptor = $convert.base64Decode('ChBHcGlvV3JpdGVSZXF1ZXN0EhkKBGdwaW8YASABKA4yBS5HcGlvUgRncGlvEhQKBXN0YXRlGAIgASgIUgVzdGF0ZQ==');
@$core.Deprecated('Use gpioWriteResponseDescriptor instead')
const GpioWriteResponse$json = const {
  '1': 'GpioWriteResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `GpioWriteResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioWriteResponseDescriptor = $convert.base64Decode('ChFHcGlvV3JpdGVSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvcg==');
@$core.Deprecated('Use gpioReadRequestDescriptor instead')
const GpioReadRequest$json = const {
  '1': 'GpioReadRequest',
  '2': const [
    const {'1': 'gpio', '3': 1, '4': 1, '5': 14, '6': '.Gpio', '10': 'gpio'},
  ],
};

/// Descriptor for `GpioReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioReadRequestDescriptor = $convert.base64Decode('Cg9HcGlvUmVhZFJlcXVlc3QSGQoEZ3BpbxgBIAEoDjIFLkdwaW9SBGdwaW8=');
@$core.Deprecated('Use gpioReadResponseDescriptor instead')
const GpioReadResponse$json = const {
  '1': 'GpioReadResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'state', '3': 3, '4': 1, '5': 8, '10': 'state'},
  ],
};

/// Descriptor for `GpioReadResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List gpioReadResponseDescriptor = $convert.base64Decode('ChBHcGlvUmVhZFJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEhQKBXN0YXRlGAMgASgIUgVzdGF0ZQ==');
@$core.Deprecated('Use adcReadRequestDescriptor instead')
const AdcReadRequest$json = const {
  '1': 'AdcReadRequest',
  '2': const [
    const {'1': 'channel', '3': 1, '4': 1, '5': 14, '6': '.AdcChannel', '10': 'channel'},
    const {'1': 'delayMs', '3': 2, '4': 1, '5': 5, '10': 'delayMs'},
  ],
};

/// Descriptor for `AdcReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List adcReadRequestDescriptor = $convert.base64Decode('Cg5BZGNSZWFkUmVxdWVzdBIlCgdjaGFubmVsGAEgASgOMgsuQWRjQ2hhbm5lbFIHY2hhbm5lbBIYCgdkZWxheU1zGAIgASgFUgdkZWxheU1z');
@$core.Deprecated('Use adcReadResponseDescriptor instead')
const AdcReadResponse$json = const {
  '1': 'AdcReadResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'voltage', '3': 3, '4': 1, '5': 1, '10': 'voltage'},
  ],
};

/// Descriptor for `AdcReadResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List adcReadResponseDescriptor = $convert.base64Decode('Cg9BZGNSZWFkUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3ISGAoHdm9sdGFnZRgDIAEoAVIHdm9sdGFnZQ==');
@$core.Deprecated('Use adcReadAllRequestDescriptor instead')
const AdcReadAllRequest$json = const {
  '1': 'AdcReadAllRequest',
  '2': const [
    const {'1': 'delayMs', '3': 1, '4': 1, '5': 5, '10': 'delayMs'},
  ],
};

/// Descriptor for `AdcReadAllRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List adcReadAllRequestDescriptor = $convert.base64Decode('ChFBZGNSZWFkQWxsUmVxdWVzdBIYCgdkZWxheU1zGAEgASgFUgdkZWxheU1z');
@$core.Deprecated('Use adcReadAllResponseDescriptor instead')
const AdcReadAllResponse$json = const {
  '1': 'AdcReadAllResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'voltage', '3': 3, '4': 3, '5': 1, '10': 'voltage'},
  ],
};

/// Descriptor for `AdcReadAllResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List adcReadAllResponseDescriptor = $convert.base64Decode('ChJBZGNSZWFkQWxsUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3ISGAoHdm9sdGFnZRgDIAMoAVIHdm9sdGFnZQ==');
@$core.Deprecated('Use uartConfigRequestDescriptor instead')
const UartConfigRequest$json = const {
  '1': 'UartConfigRequest',
  '2': const [
    const {'1': 'port', '3': 1, '4': 1, '5': 14, '6': '.UartPort', '10': 'port'},
    const {'1': 'baud', '3': 2, '4': 1, '5': 14, '6': '.UartBaudRate', '10': 'baud'},
    const {'1': 'enable', '3': 3, '4': 1, '5': 8, '10': 'enable'},
  ],
};

/// Descriptor for `UartConfigRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List uartConfigRequestDescriptor = $convert.base64Decode('ChFVYXJ0Q29uZmlnUmVxdWVzdBIdCgRwb3J0GAEgASgOMgkuVWFydFBvcnRSBHBvcnQSIQoEYmF1ZBgCIAEoDjINLlVhcnRCYXVkUmF0ZVIEYmF1ZBIWCgZlbmFibGUYAyABKAhSBmVuYWJsZQ==');
@$core.Deprecated('Use uartConfigResponseDescriptor instead')
const UartConfigResponse$json = const {
  '1': 'UartConfigResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `UartConfigResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List uartConfigResponseDescriptor = $convert.base64Decode('ChJVYXJ0Q29uZmlnUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3I=');
@$core.Deprecated('Use uartStreamRequestDescriptor instead')
const UartStreamRequest$json = const {
  '1': 'UartStreamRequest',
  '2': const [
    const {'1': 'data', '3': 1, '4': 1, '5': 12, '10': 'data'},
  ],
};

/// Descriptor for `UartStreamRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List uartStreamRequestDescriptor = $convert.base64Decode('ChFVYXJ0U3RyZWFtUmVxdWVzdBISCgRkYXRhGAEgASgMUgRkYXRh');
@$core.Deprecated('Use uartStreamResponseDescriptor instead')
const UartStreamResponse$json = const {
  '1': 'UartStreamResponse',
  '2': const [
    const {'1': 'data', '3': 1, '4': 1, '5': 12, '10': 'data'},
    const {'1': 'success', '3': 2, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 3, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `UartStreamResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List uartStreamResponseDescriptor = $convert.base64Decode('ChJVYXJ0U3RyZWFtUmVzcG9uc2USEgoEZGF0YRgBIAEoDFIEZGF0YRIYCgdzdWNjZXNzGAIgASgIUgdzdWNjZXNzEhQKBWVycm9yGAMgASgJUgVlcnJvcg==');
@$core.Deprecated('Use listFwFilesRequestDescriptor instead')
const ListFwFilesRequest$json = const {
  '1': 'ListFwFilesRequest',
};

/// Descriptor for `ListFwFilesRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List listFwFilesRequestDescriptor = $convert.base64Decode('ChJMaXN0RndGaWxlc1JlcXVlc3Q=');
@$core.Deprecated('Use fwFileInfoDescriptor instead')
const FwFileInfo$json = const {
  '1': 'FwFileInfo',
  '2': const [
    const {'1': 'name', '3': 1, '4': 1, '5': 9, '10': 'name'},
    const {'1': 'size_kb', '3': 2, '4': 1, '5': 3, '10': 'sizeKb'},
    const {'1': 'sha256_digest', '3': 3, '4': 1, '5': 9, '10': 'sha256Digest'},
  ],
};

/// Descriptor for `FwFileInfo`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List fwFileInfoDescriptor = $convert.base64Decode('CgpGd0ZpbGVJbmZvEhIKBG5hbWUYASABKAlSBG5hbWUSFwoHc2l6ZV9rYhgCIAEoA1IGc2l6ZUtiEiMKDXNoYTI1Nl9kaWdlc3QYAyABKAlSDHNoYTI1NkRpZ2VzdA==');
@$core.Deprecated('Use listFwFilesResponseDescriptor instead')
const ListFwFilesResponse$json = const {
  '1': 'ListFwFilesResponse',
  '2': const [
    const {'1': 'files', '3': 1, '4': 3, '5': 11, '6': '.FwFileInfo', '10': 'files'},
  ],
};

/// Descriptor for `ListFwFilesResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List listFwFilesResponseDescriptor = $convert.base64Decode('ChNMaXN0RndGaWxlc1Jlc3BvbnNlEiEKBWZpbGVzGAEgAygLMgsuRndGaWxlSW5mb1IFZmlsZXM=');
@$core.Deprecated('Use uploadFwFileRequestDescriptor instead')
const UploadFwFileRequest$json = const {
  '1': 'UploadFwFileRequest',
  '2': const [
    const {'1': 'filename', '3': 1, '4': 1, '5': 9, '10': 'filename'},
    const {'1': 'content', '3': 2, '4': 1, '5': 12, '10': 'content'},
  ],
};

/// Descriptor for `UploadFwFileRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List uploadFwFileRequestDescriptor = $convert.base64Decode('ChNVcGxvYWRGd0ZpbGVSZXF1ZXN0EhoKCGZpbGVuYW1lGAEgASgJUghmaWxlbmFtZRIYCgdjb250ZW50GAIgASgMUgdjb250ZW50');
@$core.Deprecated('Use uploadFwFileResponseDescriptor instead')
const UploadFwFileResponse$json = const {
  '1': 'UploadFwFileResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'sha256_digest', '3': 3, '4': 1, '5': 9, '10': 'sha256Digest'},
  ],
};

/// Descriptor for `UploadFwFileResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List uploadFwFileResponseDescriptor = $convert.base64Decode('ChRVcGxvYWRGd0ZpbGVSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvchIjCg1zaGEyNTZfZGlnZXN0GAMgASgJUgxzaGEyNTZEaWdlc3Q=');
@$core.Deprecated('Use deleteFwFileRequestDescriptor instead')
const DeleteFwFileRequest$json = const {
  '1': 'DeleteFwFileRequest',
  '2': const [
    const {'1': 'filename', '3': 1, '4': 1, '5': 9, '10': 'filename'},
  ],
};

/// Descriptor for `DeleteFwFileRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List deleteFwFileRequestDescriptor = $convert.base64Decode('ChNEZWxldGVGd0ZpbGVSZXF1ZXN0EhoKCGZpbGVuYW1lGAEgASgJUghmaWxlbmFtZQ==');
@$core.Deprecated('Use deleteFwFileResponseDescriptor instead')
const DeleteFwFileResponse$json = const {
  '1': 'DeleteFwFileResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `DeleteFwFileResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List deleteFwFileResponseDescriptor = $convert.base64Decode('ChREZWxldGVGd0ZpbGVSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvcg==');
@$core.Deprecated('Use flashHexFileRequestDescriptor instead')
const FlashHexFileRequest$json = const {
  '1': 'FlashHexFileRequest',
  '2': const [
    const {'1': 'fileName', '3': 1, '4': 1, '5': 9, '10': 'fileName'},
    const {'1': 'device', '3': 2, '4': 1, '5': 14, '6': '.DeviceType', '10': 'device'},
    const {'1': 'isModemFw', '3': 3, '4': 1, '5': 8, '10': 'isModemFw'},
  ],
};

/// Descriptor for `FlashHexFileRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List flashHexFileRequestDescriptor = $convert.base64Decode('ChNGbGFzaEhleEZpbGVSZXF1ZXN0EhoKCGZpbGVOYW1lGAEgASgJUghmaWxlTmFtZRIjCgZkZXZpY2UYAiABKA4yCy5EZXZpY2VUeXBlUgZkZXZpY2USHAoJaXNNb2RlbUZ3GAMgASgIUglpc01vZGVtRnc=');
@$core.Deprecated('Use flashHexFileResponseDescriptor instead')
const FlashHexFileResponse$json = const {
  '1': 'FlashHexFileResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'timeMs', '3': 3, '4': 1, '5': 5, '10': 'timeMs'},
  ],
};

/// Descriptor for `FlashHexFileResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List flashHexFileResponseDescriptor = $convert.base64Decode('ChRGbGFzaEhleEZpbGVSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvchIWCgZ0aW1lTXMYAyABKAVSBnRpbWVNcw==');
@$core.Deprecated('Use dutPowerEnableRequestDescriptor instead')
const DutPowerEnableRequest$json = const {
  '1': 'DutPowerEnableRequest',
  '2': const [
    const {'1': 'enable', '3': 1, '4': 1, '5': 8, '10': 'enable'},
  ],
};

/// Descriptor for `DutPowerEnableRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutPowerEnableRequestDescriptor = $convert.base64Decode('ChVEdXRQb3dlckVuYWJsZVJlcXVlc3QSFgoGZW5hYmxlGAEgASgIUgZlbmFibGU=');
@$core.Deprecated('Use dutPowerEnableResponseDescriptor instead')
const DutPowerEnableResponse$json = const {
  '1': 'DutPowerEnableResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `DutPowerEnableResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutPowerEnableResponseDescriptor = $convert.base64Decode('ChZEdXRQb3dlckVuYWJsZVJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9y');
@$core.Deprecated('Use dutVoltageSetRequestDescriptor instead')
const DutVoltageSetRequest$json = const {
  '1': 'DutVoltageSetRequest',
  '2': const [
    const {'1': 'voltage', '3': 1, '4': 1, '5': 1, '10': 'voltage'},
  ],
};

/// Descriptor for `DutVoltageSetRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutVoltageSetRequestDescriptor = $convert.base64Decode('ChREdXRWb2x0YWdlU2V0UmVxdWVzdBIYCgd2b2x0YWdlGAEgASgBUgd2b2x0YWdl');
@$core.Deprecated('Use dutVoltageSetResponseDescriptor instead')
const DutVoltageSetResponse$json = const {
  '1': 'DutVoltageSetResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `DutVoltageSetResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutVoltageSetResponseDescriptor = $convert.base64Decode('ChVEdXRWb2x0YWdlU2V0UmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3I=');
@$core.Deprecated('Use dutCurrentReadRequestDescriptor instead')
const DutCurrentReadRequest$json = const {
  '1': 'DutCurrentReadRequest',
};

/// Descriptor for `DutCurrentReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutCurrentReadRequestDescriptor = $convert.base64Decode('ChVEdXRDdXJyZW50UmVhZFJlcXVlc3Q=');
@$core.Deprecated('Use dutCurrentReadResponseDescriptor instead')
const DutCurrentReadResponse$json = const {
  '1': 'DutCurrentReadResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'current_ma', '3': 3, '4': 1, '5': 5, '10': 'currentMa'},
  ],
};

/// Descriptor for `DutCurrentReadResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutCurrentReadResponseDescriptor = $convert.base64Decode('ChZEdXRDdXJyZW50UmVhZFJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEh0KCmN1cnJlbnRfbWEYAyABKAVSCWN1cnJlbnRNYQ==');
@$core.Deprecated('Use dutVoltageReadRequestDescriptor instead')
const DutVoltageReadRequest$json = const {
  '1': 'DutVoltageReadRequest',
};

/// Descriptor for `DutVoltageReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutVoltageReadRequestDescriptor = $convert.base64Decode('ChVEdXRWb2x0YWdlUmVhZFJlcXVlc3Q=');
@$core.Deprecated('Use dutVoltageReadResponseDescriptor instead')
const DutVoltageReadResponse$json = const {
  '1': 'DutVoltageReadResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'voltage_mv', '3': 3, '4': 1, '5': 5, '10': 'voltageMv'},
  ],
};

/// Descriptor for `DutVoltageReadResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutVoltageReadResponseDescriptor = $convert.base64Decode('ChZEdXRWb2x0YWdlUmVhZFJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9yEh0KCnZvbHRhZ2VfbXYYAyABKAVSCXZvbHRhZ2VNdg==');
@$core.Deprecated('Use dutPowerReadRequestDescriptor instead')
const DutPowerReadRequest$json = const {
  '1': 'DutPowerReadRequest',
};

/// Descriptor for `DutPowerReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutPowerReadRequestDescriptor = $convert.base64Decode('ChNEdXRQb3dlclJlYWRSZXF1ZXN0');
@$core.Deprecated('Use dutPowerReadResponseDescriptor instead')
const DutPowerReadResponse$json = const {
  '1': 'DutPowerReadResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'power_mw', '3': 3, '4': 1, '5': 5, '10': 'powerMw'},
  ],
};

/// Descriptor for `DutPowerReadResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List dutPowerReadResponseDescriptor = $convert.base64Decode('ChREdXRQb3dlclJlYWRSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvchIZCghwb3dlcl9tdxgDIAEoBVIHcG93ZXJNdw==');
@$core.Deprecated('Use altimeterReadRequestDescriptor instead')
const AltimeterReadRequest$json = const {
  '1': 'AltimeterReadRequest',
};

/// Descriptor for `AltimeterReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List altimeterReadRequestDescriptor = $convert.base64Decode('ChRBbHRpbWV0ZXJSZWFkUmVxdWVzdA==');
@$core.Deprecated('Use altimeterReadResponseDescriptor instead')
const AltimeterReadResponse$json = const {
  '1': 'AltimeterReadResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'temperature_f', '3': 3, '4': 1, '5': 1, '10': 'temperatureF'},
    const {'1': 'pressure_hg', '3': 4, '4': 1, '5': 1, '10': 'pressureHg'},
    const {'1': 'altitude_ft', '3': 5, '4': 1, '5': 1, '10': 'altitudeFt'},
  ],
};

/// Descriptor for `AltimeterReadResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List altimeterReadResponseDescriptor = $convert.base64Decode('ChVBbHRpbWV0ZXJSZWFkUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3ISIwoNdGVtcGVyYXR1cmVfZhgDIAEoAVIMdGVtcGVyYXR1cmVGEh8KC3ByZXNzdXJlX2hnGAQgASgBUgpwcmVzc3VyZUhnEh8KC2FsdGl0dWRlX2Z0GAUgASgBUgphbHRpdHVkZUZ0');
@$core.Deprecated('Use accelReadRequestDescriptor instead')
const AccelReadRequest$json = const {
  '1': 'AccelReadRequest',
};

/// Descriptor for `AccelReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List accelReadRequestDescriptor = $convert.base64Decode('ChBBY2NlbFJlYWRSZXF1ZXN0');
@$core.Deprecated('Use accelReadResponseDescriptor instead')
const AccelReadResponse$json = const {
  '1': 'AccelReadResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'x', '3': 3, '4': 1, '5': 1, '10': 'x'},
    const {'1': 'y', '3': 4, '4': 1, '5': 1, '10': 'y'},
    const {'1': 'z', '3': 5, '4': 1, '5': 1, '10': 'z'},
  ],
};

/// Descriptor for `AccelReadResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List accelReadResponseDescriptor = $convert.base64Decode('ChFBY2NlbFJlYWRSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvchIMCgF4GAMgASgBUgF4EgwKAXkYBCABKAFSAXkSDAoBehgFIAEoAVIBeg==');
@$core.Deprecated('Use accelReadMaxRequestDescriptor instead')
const AccelReadMaxRequest$json = const {
  '1': 'AccelReadMaxRequest',
};

/// Descriptor for `AccelReadMaxRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List accelReadMaxRequestDescriptor = $convert.base64Decode('ChNBY2NlbFJlYWRNYXhSZXF1ZXN0');
@$core.Deprecated('Use accelReadMaxResponseDescriptor instead')
const AccelReadMaxResponse$json = const {
  '1': 'AccelReadMaxResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'max', '3': 3, '4': 1, '5': 1, '10': 'max'},
  ],
};

/// Descriptor for `AccelReadMaxResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List accelReadMaxResponseDescriptor = $convert.base64Decode('ChRBY2NlbFJlYWRNYXhSZXNwb25zZRIYCgdzdWNjZXNzGAEgASgIUgdzdWNjZXNzEhQKBWVycm9yGAIgASgJUgVlcnJvchIQCgNtYXgYAyABKAFSA21heA==');
@$core.Deprecated('Use eepromReadRequestDescriptor instead')
const EepromReadRequest$json = const {
  '1': 'EepromReadRequest',
  '2': const [
    const {'1': 'address', '3': 2, '4': 1, '5': 5, '10': 'address'},
    const {'1': 'len', '3': 3, '4': 1, '5': 5, '10': 'len'},
  ],
};

/// Descriptor for `EepromReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List eepromReadRequestDescriptor = $convert.base64Decode('ChFFZXByb21SZWFkUmVxdWVzdBIYCgdhZGRyZXNzGAIgASgFUgdhZGRyZXNzEhAKA2xlbhgDIAEoBVIDbGVu');
@$core.Deprecated('Use eepromReadResponseDescriptor instead')
const EepromReadResponse$json = const {
  '1': 'EepromReadResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
    const {'1': 'data', '3': 3, '4': 1, '5': 12, '10': 'data'},
  ],
};

/// Descriptor for `EepromReadResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List eepromReadResponseDescriptor = $convert.base64Decode('ChJFZXByb21SZWFkUmVzcG9uc2USGAoHc3VjY2VzcxgBIAEoCFIHc3VjY2VzcxIUCgVlcnJvchgCIAEoCVIFZXJyb3ISEgoEZGF0YRgDIAEoDFIEZGF0YQ==');
@$core.Deprecated('Use eepromWriteRequestDescriptor instead')
const EepromWriteRequest$json = const {
  '1': 'EepromWriteRequest',
  '2': const [
    const {'1': 'buffer', '3': 1, '4': 1, '5': 12, '10': 'buffer'},
    const {'1': 'address', '3': 2, '4': 1, '5': 5, '10': 'address'},
    const {'1': 'len', '3': 3, '4': 1, '5': 5, '10': 'len'},
  ],
};

/// Descriptor for `EepromWriteRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List eepromWriteRequestDescriptor = $convert.base64Decode('ChJFZXByb21Xcml0ZVJlcXVlc3QSFgoGYnVmZmVyGAEgASgMUgZidWZmZXISGAoHYWRkcmVzcxgCIAEoBVIHYWRkcmVzcxIQCgNsZW4YAyABKAVSA2xlbg==');
@$core.Deprecated('Use eepromWriteResponseDescriptor instead')
const EepromWriteResponse$json = const {
  '1': 'EepromWriteResponse',
  '2': const [
    const {'1': 'success', '3': 1, '4': 1, '5': 8, '10': 'success'},
    const {'1': 'error', '3': 2, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `EepromWriteResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List eepromWriteResponseDescriptor = $convert.base64Decode('ChNFZXByb21Xcml0ZVJlc3BvbnNlEhgKB3N1Y2Nlc3MYASABKAhSB3N1Y2Nlc3MSFAoFZXJyb3IYAiABKAlSBWVycm9y');

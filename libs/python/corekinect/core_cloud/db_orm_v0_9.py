# coding: utf-8
from sqlalchemy import BigInteger, CHAR, Column, DateTime, Float, Index, Integer, String, TIMESTAMP, text
from sqlalchemy.dialects.mysql import BIT, DATETIME
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata


class AccountTypesTbl(Base):
    __tablename__ = 'AccountTypesTbl'

    AccountTypeId = Column(Integer, primary_key=True, unique=True)
    AccountTypeName = Column(String(48), nullable=False)


class AccountsTbl(Base):
    __tablename__ = 'AccountsTbl'

    AccountId = Column(Integer, primary_key=True, unique=True)
    AccountName = Column(String(64), nullable=False)
    AccountTypeId = Column(Integer, nullable=False)
    DateTimeCreatedUtc = Column(DateTime, nullable=False)
    DateTimeDeactivatedUtc = Column(DateTime)
    IsActive = Column(BIT(1), nullable=False)


class AckMessageTbl(Base):
    __tablename__ = 'AckMessageTbl'

    AckMessageId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DATETIME(fsp=3), nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    IsAck = Column(BIT(1), nullable=False)
    Nonce = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class BleBeaconAssTbl(Base):
    __tablename__ = 'BleBeaconAssTbl'

    BleBeaconAssTblId = Column(BigInteger, primary_key=True)
    BeaconId = Column(BigInteger, nullable=False, index=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    LastRssi = Column(Integer, nullable=False)
    LastRssiTime = Column(DateTime, nullable=False)
    StartAss = Column(DateTime, nullable=False, index=True)
    StopAss = Column(DateTime, index=True)


class BleBeaconLocTbl(Base):
    __tablename__ = 'BleBeaconLocTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    BeaconXyWeight = Column(Float(asdecimal=True), nullable=False, server_default=text("'1'"))
    BeaconFloor = Column(Integer, nullable=False)
    BeaconFloorWeight = Column(Float(asdecimal=True), nullable=False, server_default=text("'1'"))
    AccountId = Column(Integer, nullable=False, index=True)


class ByteBufferTransferMessageICLETbl(Base):
    __tablename__ = 'ByteBufferTransferMessageICLETbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DATETIME(fsp=3), nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class CertificatesTbl(Base):
    __tablename__ = 'CertificatesTbl'

    CertificatesTblId = Column(Integer, primary_key=True)
    AccountId = Column(Integer, nullable=False, index=True)
    CertificateName = Column(String(64), nullable=False)
    FileName = Column(String(64), nullable=False)
    FilePath = Column(String(256), nullable=False)
    Subject = Column(String(64), nullable=False)
    Issuer = Column(String(64), nullable=False)
    ValidFrom = Column(DateTime)
    ValidTo = Column(DateTime)
    Secret = Column(String(832), nullable=False)


class ConfigurationMessageDownlinkTankTrackTbl(Base):
    __tablename__ = 'ConfigurationMessageDownlinkTankTrackTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    Flags = Column(Integer, nullable=False)
    StartMotionMessageEnabled = Column(BIT(1), nullable=False)
    AccelerometerEnabled = Column(BIT(1), nullable=False)
    ReedSwitchEnabled = Column(BIT(1), nullable=False)
    InMotionMeasurementPeriod = Column(Integer, nullable=False)
    HeartbeatMeasurementPeriod = Column(Integer, nullable=False)
    HeartbeatReportInterval = Column(Integer, nullable=False)
    Alarm1Threshold = Column(Integer, nullable=False)
    Alarm2Threshold = Column(Integer, nullable=False)
    Alarm3Threshold = Column(Integer, nullable=False)
    AlarmHysteresis = Column(Integer, nullable=False)
    AccThresh = Column(Integer, nullable=False)
    AccDur = Column(Integer, nullable=False)
    AccStopMotion = Column(Integer, nullable=False)
    AdcMeasurementTime = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)
    DownlinkMessageId = Column(BigInteger, nullable=False)


class ConfigurationMessageTankTrackTbl(Base):
    __tablename__ = 'ConfigurationMessageTankTrackTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    StartMotionMessageEnabled = Column(BIT(1), nullable=False)
    AccelerometerEnabled = Column(BIT(1), nullable=False)
    ReedSwitchEnabled = Column(BIT(1), nullable=False)
    InMotionMeasurementPeriod = Column(Integer, nullable=False)
    HeartbeatMeasurementPeriod = Column(Integer, nullable=False)
    HeartbeatReportInterval = Column(Integer, nullable=False)
    Alarm1Threshold = Column(Integer, nullable=False)
    Alarm2Threshold = Column(Integer, nullable=False)
    Alarm3Threshold = Column(Integer, nullable=False)
    AlarmHysteresis = Column(Integer, nullable=False)
    AccThresh = Column(Integer, nullable=False)
    AccDur = Column(Integer, nullable=False)
    AccStopMotion = Column(Integer, nullable=False)
    AdcMeasurementTime = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class CoreTrackGatewayFirmwareMsgTbl(Base):
    __tablename__ = 'CoreTrackGatewayFirmwareMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Bootloader9160Version = Column(Integer, nullable=False)
    Application9160Version = Column(Integer, nullable=False)
    Bootloader52840Version = Column(Integer, nullable=False)
    Application52840Version = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class CoreTrackGatewayKeysTbl(Base):
    __tablename__ = 'CoreTrackGatewayKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)


class CoreTrackGatewayLastNonceTbl(Base):
    __tablename__ = 'CoreTrackGatewayLastNonceTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    LastNonce = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)


class DefaultTagCheckinsTbl(Base):
    __tablename__ = 'DefaultTagCheckinsTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    Rssi = Column(Integer, nullable=False)
    EncryptedData = Column(String(5464), nullable=False)
    AccountId = Column(Integer, nullable=False)
    GatewayId = Column(BigInteger, nullable=False)
    DataSource = Column(Integer, server_default=text("'1'"))
    Longitude = Column(Float(asdecimal=True))
    latitude = Column(Float(asdecimal=True))


class DeviceEndpointsTbl(Base):
    __tablename__ = 'DeviceEndpointsTbl'

    DeviceEndpointId = Column(BigInteger, primary_key=True, unique=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    EndpointId = Column(BigInteger, nullable=False)
    IsActive = Column(BIT(1), nullable=False)
    Associated = Column(DateTime, nullable=False)
    Disassociated = Column(DateTime)
    AccountId = Column(Integer, nullable=False)


class DeviceTypesTbl(Base):
    __tablename__ = 'DeviceTypesTbl'

    DeviceTypeId = Column(Integer, primary_key=True, unique=True)
    DeviceTypeString = Column(String(32), nullable=False, unique=True)
    DeviceDataTblName = Column(String(48))
    DeviceKeysTblName = Column(String(48))
    DeviceKeysArchiveTblName = Column(String(48))


class DevicesArchiveTbl(Base):
    __tablename__ = 'DevicesArchiveTbl'

    DevicesArchiveTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False)
    DevVariantId = Column(Integer, nullable=False, server_default=text("'0'"))
    IsActive = Column(BIT(1), nullable=False)
    IsAssigned = Column(BIT(1), nullable=False)
    AddedTimeUtc = Column(DateTime, nullable=False)
    DateTimeArchivedUtc = Column(DateTime)


class DevicesTbl(Base):
    __tablename__ = 'DevicesTbl'

    DeviceTblId = Column(BigInteger, nullable=False, unique=True)
    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    AccountId = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)
    IsActive = Column(BIT(1), nullable=False)
    IsAssigned = Column(BIT(1), nullable=False)
    AddedTimeUtc = Column(DateTime, nullable=False)
    DeletedTimeUtc = Column(DateTime)
    DevVariantId = Column(Integer, nullable=False, server_default=text("'0'"))


class DistFromTbl(Base):
    __tablename__ = 'DistFromTbl'

    DistFromTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False)
    ActLat = Column(Float(asdecimal=True), nullable=False)
    ActLon = Column(Float(asdecimal=True), nullable=False)
    DistOff = Column(Float(asdecimal=True), nullable=False)
    LoRaLocEstTblId = Column(BigInteger, nullable=False)
    TimeRx = Column(DateTime, nullable=False)
    CalculationType = Column(Integer, nullable=False)


class DownlinkMessagesTbl(Base):
    __tablename__ = 'DownlinkMessagesTbl'

    DownlinkMessageId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    TimeQueued = Column(DateTime, nullable=False)
    NonceSent = Column(Integer, nullable=False)
    IsAcked = Column(BIT(1), nullable=False)
    IsNaked = Column(BIT(1), nullable=False)
    Message = Column(String(4096), nullable=False)
    AccountId = Column(Integer, nullable=False)


class EndpointsTbl(Base):
    __tablename__ = 'EndpointsTbl'

    EndpointId = Column(BigInteger, primary_key=True, unique=True)
    AccountId = Column(Integer, nullable=False)
    EndpointUrl = Column(String(256), nullable=False)
    AuthUrl = Column(String(256))
    Auth = Column(String(832))
    AuthToken = Column(String(832))
    AuthTokenKey = Column(String(64))
    AuthTokenType = Column(String(64))
    AuthTokenExpiration = Column(DateTime)
    AuthTokenExpirationKey = Column(String(64))
    AuthTokenUpdated = Column(DateTime)
    EncryptionType = Column(Integer, nullable=False)
    IsActive = Column(BIT(1), nullable=False)
    ConsecutiveFails = Column(Integer, nullable=False)
    Priority = Column(Integer, nullable=False, server_default=text("'0'"))


class EnvironmentsTbl(Base):
    __tablename__ = 'EnvironmentsTbl'

    EnvironmentsTblId = Column(Integer, primary_key=True)
    EnvironmentKey = Column(String(64), nullable=False)
    EnvironmentValue = Column(String(64), nullable=False)


class ErrorCodeTbl(Base):
    __tablename__ = 'ErrorCodeTbl'

    ErrorCode = Column(Integer, primary_key=True)
    ErrorMessage = Column(String(50))


class FirmwareImagesTbl(Base):
    __tablename__ = 'FirmwareImagesTbl'

    FwVersionInfo = Column(Integer, primary_key=True)
    FwCrc = Column(Integer, nullable=False)
    ImageLength = Column(Integer, nullable=False)
    FwType = Column(Integer, nullable=False)
    FwVersion = Column(Integer, nullable=False)
    IsGoldenImage = Column(BIT(1), nullable=False)
    IsProductionImage = Column(BIT(1), nullable=False)
    Filename = Column(String(40), nullable=False)


class FirmwareMessageICLETbl(Base):
    __tablename__ = 'FirmwareMessageICLETbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    BootloaderVersion = Column(Integer, nullable=False)
    ApplicationVersion = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class FirmwareMessageTankTrackTbl(Base):
    __tablename__ = 'FirmwareMessageTankTrackTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    BootloaderVersion = Column(Integer, nullable=False)
    ApplicationVersion = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class FirmwareUpdateMessageTbl(Base):
    __tablename__ = 'FirmwareUpdateMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    NumberOfPages = Column(Integer, nullable=False)
    FirmwareVersion = Column(Integer, nullable=False)
    ImageChecksum = Column(Integer, nullable=False)
    ImageChunkLength = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)
    CurrentPage = Column(Integer, nullable=False)


class FirmwareUpdatePrepareMsgTbl(Base):
    __tablename__ = 'FirmwareUpdatePrepareMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    FirmwareVersion = Column(Integer, nullable=False)
    NumberOfBytes = Column(Integer, nullable=False)
    ImageChecksum = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class FirmwareUpdateResetMessageTbl(Base):
    __tablename__ = 'FirmwareUpdateResetMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    ResetKey = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class FirmwareUpdateResponseMessageTbl(Base):
    __tablename__ = 'FirmwareUpdateResponseMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    FirmwareDownloadVersion = Column(Integer, nullable=False)
    NextPageRequested = Column(Integer, nullable=False)
    NumberOfChunksRequested = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class FirmwareUpdateV2MsgTbl(Base):
    __tablename__ = 'FirmwareUpdateV2MsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    CurrentPage = Column(Integer, nullable=False)
    NumBytesSent = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class ForwardFailTbl(Base):
    __tablename__ = 'ForwardFailTbl'

    ForwardFailTblId = Column(BigInteger, primary_key=True)
    DeviceEndpointId = Column(BigInteger, nullable=False)
    EndpointId = Column(BigInteger)
    CheckInId = Column(BigInteger, nullable=False)
    FailedTime = Column(DateTime, nullable=False)
    TimeToForward = Column(BigInteger)
    NumberAttempts = Column(Integer, nullable=False)
    HttpResponse = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer)
    MessageTypeId = Column(Integer)


class ForwardSuccessTbl(Base):
    __tablename__ = 'ForwardSuccessTbl'

    ForwardSuccessTblId = Column(BigInteger, primary_key=True)
    DeviceEndpointId = Column(BigInteger, nullable=False)
    EndpointId = Column(BigInteger)
    CheckInId = Column(BigInteger, nullable=False)
    ForwardTime = Column(DateTime, nullable=False)
    TimeToForward = Column(BigInteger)
    AccountId = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer)
    MessageTypeId = Column(Integer)


class FreshTrackCheckinsTbl(Base):
    __tablename__ = 'FreshTrackCheckinsTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    Rssi = Column(Integer, nullable=False)
    EncryptedData = Column(String(5464), nullable=False)
    AccountId = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True))
    Longitude = Column(Float(asdecimal=True))
    GatewayId = Column(BigInteger, nullable=False)
    DataSource = Column(Integer, server_default=text("'1'"))


class FreshTrackTemperatureOffsetTbl(Base):
    __tablename__ = 'FreshTrackTemperatureOffsetTbl'

    OffsetId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TempOffset = Column(Float(asdecimal=True))


class FuotaListsTbl(Base):
    __tablename__ = 'FuotaListsTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    ReleaseList = Column(Integer, nullable=False)


class FuotaReleaseListDescriptionTbl(Base):
    __tablename__ = 'FuotaReleaseListDescriptionTbl'

    ReleaseList = Column(Integer, primary_key=True, unique=True)
    Description = Column(String(256), nullable=False)


class FuotaTbl(Base):
    __tablename__ = 'FuotaTbl'

    FuotaId = Column(BigInteger, primary_key=True)
    DeviceTypeId = Column(Integer, nullable=False)
    IsActive = Column(BIT(1), nullable=False)
    FwVersion = Column(Integer, nullable=False)
    FilePath = Column(String(255), nullable=False)
    ReleaseList = Column(Integer, nullable=False)
    Released = Column(BIT(1), nullable=False)


class ICLEKeysTbl(Base):
    __tablename__ = 'ICLEKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)


class ICLELastNonceTbl(Base):
    __tablename__ = 'ICLELastNonceTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    LastNonce = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)


class IclePowerTbl(Base):
    __tablename__ = 'IclePowerTbl'
    __table_args__ = (
        Index('IclePowerTbl_DeviceId', 'DeviceId', 'Channel'),
    )

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False)
    TimeStamp = Column(DateTime, nullable=False, index=True)
    Channel = Column(Integer, nullable=False)
    Current = Column(Float(asdecimal=True), nullable=False)
    Voltage = Column(Float(asdecimal=True), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class IssuesTbl(Base):
    __tablename__ = 'IssuesTbl'

    IssuesTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    ErrorCode = Column(Integer, nullable=False)


class JumpTrack1CMsgTbl(Base):
    __tablename__ = 'JumpTrack1CMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1))
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AltitudeGps = Column(Integer, nullable=False)
    AltitudeCalculated = Column(Integer, nullable=False)
    GroundSpeed = Column(Integer, nullable=False)
    Heading = Column(Integer, nullable=False)
    TimeOfFix = Column(DateTime, nullable=False, index=True)
    BatteryVoltage = Column(Integer)
    BatteryPercentage = Column(Integer)
    AirPressureInHg = Column(Float(asdecimal=True), nullable=False)
    Temperature = Column(Float(asdecimal=True), nullable=False)
    AverageForce = Column(Float(asdecimal=True))
    MaxForce = Column(Float(asdecimal=True))
    AccountId = Column(Integer, nullable=False, index=True)
    DataSource = Column(Integer, nullable=False)
    Crc = Column(Integer, nullable=False)
    NonceReceived = Column(Integer)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)
    FixType = Column(Integer)
    NumSatellites = Column(Integer)
    PsmState = Column(Integer)
    Pdop = Column(Integer)
    BmsTemp = Column(Integer)
    GpsVertAccuracy = Column(Integer)
    EmergencyEventId = Column(Integer)


class JumpTrackBeaconAssTbl(Base):
    __tablename__ = 'JumpTrackBeaconAssTbl'

    BeaconAssTblId = Column(BigInteger, primary_key=True)
    BeaconId = Column(BigInteger, nullable=False, index=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    LastRssi = Column(Integer, nullable=False)
    LastRssiTime = Column(DateTime, nullable=False)
    StartAss = Column(DateTime, nullable=False, index=True)
    StopAss = Column(DateTime, index=True)


class JumpTrackBeaconCheckinTbl(Base):
    __tablename__ = 'JumpTrackBeaconCheckinTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    BeaconId = Column(BigInteger, nullable=False, index=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AltitudeCalculated = Column(Integer, nullable=False)
    GroundSpeed = Column(Integer, nullable=False)
    Heading = Column(Integer, nullable=False)
    TimeOfFix = Column(DateTime, nullable=False, index=True)
    Rssi = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackBiometricMsgTbl(Base):
    __tablename__ = 'JumpTrackBiometricMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfData = Column(DateTime, nullable=False, index=True)
    NumHeartrateSamp = Column(Integer, nullable=False)
    MaxHeartrate = Column(Integer, nullable=False)
    MinHeartrate = Column(Integer, nullable=False)
    AvgHeartrate = Column(Integer, nullable=False)
    PulseOxPercent = Column(Integer, nullable=False)
    TimeOfPulseOx = Column(DateTime, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackBleBeaconConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackBleBeaconConfigMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfConfig = Column(DateTime, nullable=False, index=True)
    Flags = Column(Integer, nullable=False)
    BeaconPeriod = Column(Integer, nullable=False)
    BeaconDuration = Column(Integer, nullable=False)
    BeaconPower = Column(Integer, nullable=False)
    BleSessionKeyCrc = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackBleKeysArchiveTbl(Base):
    __tablename__ = 'JumpTrackBleKeysArchiveTbl'

    Id = Column(Integer, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)
    DateTimeArchivedUtc = Column(DateTime, nullable=False)


class JumpTrackBleKeysTbl(Base):
    __tablename__ = 'JumpTrackBleKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)


class JumpTrackBleLabelMsgTbl(Base):
    __tablename__ = 'JumpTrackBleLabelMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    FromDeviceId = Column(BigInteger, nullable=False)
    GroupId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    TimeNameAssigned = Column(DateTime, nullable=False, index=True)
    Label = Column(String(16), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackBootMessageTbl(Base):
    __tablename__ = 'JumpTrackBootMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    BootReason = Column(Integer, nullable=False)
    NumberOfExceptions = Column(Integer, nullable=False)
    TimeOfBoot = Column(DateTime, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackConfigDownlinkMsgTbl(Base):
    __tablename__ = 'JumpTrackConfigDownlinkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    GpsHeartbeatPeriod = Column(Integer, nullable=False)
    ContMotionPeriod = Column(Integer, nullable=False)
    StopMotionPeriod = Column(Integer, nullable=False)
    HeartbeatAcqTimeout = Column(Integer, nullable=False)
    MotionAcqTimeout = Column(Integer, nullable=False)
    JumpStateGpsPeriod = Column(Integer, nullable=False)
    JumpStateTime = Column(Integer, nullable=False)
    MotionThreshold = Column(Integer, nullable=False)
    MotionDuration = Column(Integer, nullable=False)
    FreeFallThreshold = Column(Integer, nullable=False)
    FreeFallDuration = Column(Integer, nullable=False)
    FreeFallAltThreshold = Column(Integer, nullable=False)
    JumpTriggerAltChange = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    DownlinkMessageId = Column(BigInteger, nullable=False, index=True)


class JumpTrackConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackConfigMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfConfig = Column(DateTime, nullable=False, index=True)
    GpsHeartbeatPeriod = Column(Integer, nullable=False)
    ContMotionPeriod = Column(Integer, nullable=False)
    StopMotionPeriod = Column(Integer, nullable=False)
    HeartbeatAcqTimeout = Column(Integer, nullable=False)
    MotionAcqTimeout = Column(Integer, nullable=False)
    JumpStateGpsPeriod = Column(Integer, nullable=False)
    JumpStateTime = Column(Integer, nullable=False)
    MotionThreshold = Column(Integer, nullable=False)
    MotionDuration = Column(Integer, nullable=False)
    FreeFallThreshold = Column(Integer, nullable=False)
    FreeFallDuration = Column(Integer, nullable=False)
    FreeFallAltThreshold = Column(Integer, nullable=False)
    JumpTriggerAltChange = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackEmerEventRespMsgTbl(Base):
    __tablename__ = 'JumpTrackEmerEventRespMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    EmergencyEventId = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class JumpTrackEmergencyConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackEmergencyConfigDnlnkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeLimit = Column(Integer, nullable=False)
    TapThreshold = Column(Integer, nullable=False)
    TapShockWindow = Column(Integer, nullable=False)
    TapQuietWindow = Column(Integer, nullable=False)
    TapLatencyWindow = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    DownlinkMessageId = Column(BigInteger, nullable=False, index=True)


class JumpTrackEmergencyConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackEmergencyConfigMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfEmConfig = Column(DateTime, nullable=False, index=True)
    TimeLimit = Column(Integer, nullable=False)
    TapThreshold = Column(Integer, nullable=False)
    TapShockWindow = Column(Integer, nullable=False)
    TapQuietWindow = Column(Integer, nullable=False)
    TapLatencyWindow = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackEmergencyConfigV2DnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackEmergencyConfigV2DnlnkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeLimit = Column(Integer, nullable=False)
    BtnActivationTime = Column(Integer, nullable=False)
    BtnTimeout = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    DownlinkMessageId = Column(BigInteger, nullable=False, index=True)


class JumpTrackEmergencyConfigV2MsgTbl(Base):
    __tablename__ = 'JumpTrackEmergencyConfigV2MsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfEmConfig = Column(DateTime, nullable=False, index=True)
    TimeLimit = Column(Integer, nullable=False)
    BtnActivationTime = Column(Integer, nullable=False)
    BtnTimeout = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackFallConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackFallConfigDnlnkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    Flags = Column(Integer, nullable=False)
    JumpStateGpsReportPeriod = Column(Integer, nullable=False)
    JumpStateTime = Column(Integer, nullable=False)
    FreeFallAccThresh = Column(Integer, nullable=False)
    FreeFallAccDur = Column(Integer, nullable=False)
    FreeFallAltChangeThresh = Column(Integer, nullable=False)
    AltChangeJumpTrig = Column(Integer, nullable=False)
    NumAltStableSamples = Column(Integer, nullable=False)
    AltStabilityThreshold = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    DownlinkMessageId = Column(BigInteger, nullable=False, index=True)


class JumpTrackFallConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackFallConfigMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfConfig = Column(DateTime, nullable=False, index=True)
    Flags = Column(Integer, nullable=False)
    JumpModeEnabled = Column(BIT(1), nullable=False)
    JumpStateGpsReportPeriod = Column(Integer, nullable=False)
    JumpStateTime = Column(Integer, nullable=False)
    FreeFallAccThresh = Column(Integer, nullable=False)
    FreeFallAccDur = Column(Integer, nullable=False)
    FreeFallAltChangeThresh = Column(Integer, nullable=False)
    AltChangeJumpTrig = Column(Integer, nullable=False)
    NumAltStableSamples = Column(Integer, nullable=False)
    AltStabilityThreshold = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackFirmwareMessageTbl(Base):
    __tablename__ = 'JumpTrackFirmwareMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    BootloaderVersion = Column(Integer, nullable=False)
    ApplicationVersion = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackFirmwareV2MessageTbl(Base):
    __tablename__ = 'JumpTrackFirmwareV2MessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Bootloader9160Version = Column(Integer, nullable=False)
    Application9160Version = Column(Integer, nullable=False)
    Bootloader52833Version = Column(Integer, nullable=False)
    Application52833Version = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackFreeFallMessageTbl(Base):
    __tablename__ = 'JumpTrackFreeFallMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    FallTime = Column(DateTime, nullable=False)
    Flags = Column(Integer)
    IsJumpModeEnabled = Column(BIT(1))
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackGndConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackGndConfigDnlnkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    GpsHeartbeatPeriod = Column(Integer, nullable=False)
    ContMotionPeriod = Column(Integer, nullable=False)
    StopMotionPeriod = Column(Integer, nullable=False)
    HeartbeatAcqTimeout = Column(Integer, nullable=False)
    MotionAcqTimeout = Column(Integer, nullable=False)
    MotionThreshold = Column(Integer, nullable=False)
    MotionDuration = Column(Integer, nullable=False)
    StartMotionWindowStart = Column(Integer, nullable=False)
    StartMotionWindowEnd = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    DownlinkMessageId = Column(BigInteger, nullable=False, index=True)


class JumpTrackGndConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackGndConfigMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfConfig = Column(DateTime, nullable=False, index=True)
    GpsHeartbeatPeriod = Column(Integer, nullable=False)
    ContMotionPeriod = Column(Integer, nullable=False)
    StopMotionPeriod = Column(Integer, nullable=False)
    HeartbeatAcqTimeout = Column(Integer, nullable=False)
    MotionAcqTimeout = Column(Integer, nullable=False)
    MotionThreshold = Column(Integer, nullable=False)
    MotionDuration = Column(Integer, nullable=False)
    StartMotionWindowStart = Column(Integer, nullable=False)
    StartMotionWindowEnd = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackGndConfigV2DnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackGndConfigV2DnlnkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    GpsHeartbeatPeriod = Column(Integer, nullable=False)
    ContMotionPeriod = Column(Integer, nullable=False)
    MotionStopTimeout = Column(Integer, nullable=False)
    HeartbeatAcqTimeout = Column(Integer, nullable=False)
    MotionAcqTimeout = Column(Integer, nullable=False)
    MotionThreshold = Column(Integer, nullable=False)
    MotionDuration = Column(Integer, nullable=False)
    StartMotionWindowStart = Column(Integer, nullable=False)
    StartMotionWindowEnd = Column(Integer, nullable=False)
    MotionAcqOnTime = Column(Integer, nullable=False)
    MotionInitAcqOnTime = Column(Integer, nullable=False)
    Reserved = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    DownlinkMessageId = Column(BigInteger, nullable=False, index=True)


class JumpTrackGndConfigV2MsgTbl(Base):
    __tablename__ = 'JumpTrackGndConfigV2MsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfConfig = Column(DateTime, nullable=False)
    GpsHeartbeatPeriod = Column(Integer, nullable=False)
    ContMotionPeriod = Column(Integer, nullable=False)
    MotionStopTimeout = Column(Integer, nullable=False)
    HeartbeatAcqTimeout = Column(Integer, nullable=False)
    MotionAcqTimeout = Column(Integer, nullable=False)
    MotionThreshold = Column(Integer, nullable=False)
    MotionDuration = Column(Integer, nullable=False)
    StartMotionWindowStart = Column(Integer, nullable=False)
    StartMotionWindowEnd = Column(Integer, nullable=False)
    MotionAcqOnTime = Column(Integer, nullable=False)
    MotionInitAcqOnTime = Column(Integer, nullable=False)
    Reserved = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class JumpTrackGpsConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackGpsConfigDnlnkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    Flags = Column(Integer, nullable=False)
    TargetFixAccuracy = Column(Integer, nullable=False)
    TargetFixPdop = Column(Integer, nullable=False)
    DownlinkMessageId = Column(BigInteger, nullable=False)
    AccountId = Column(Integer, nullable=False)


class JumpTrackGpsConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackGpsConfigMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfGpsConfig = Column(DateTime, nullable=False, index=True)
    Flags = Column(Integer, nullable=False)
    TargetFixAccuracy = Column(Integer, nullable=False)
    TargetFixPdop = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackGroupDevicesTbl(Base):
    __tablename__ = 'JumpTrackGroupDevicesTbl'

    JumpTrackGroupDevicesTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, unique=True)
    GroupId = Column(BigInteger, nullable=False, index=True)
    AddedToGroup = Column(DateTime, nullable=False)
    AcceptedGroup = Column(DateTime)
    AccountId = Column(Integer, nullable=False)


class JumpTrackGroupJoinTbl(Base):
    __tablename__ = 'JumpTrackGroupJoinTbl'

    JoinRequestId = Column(BigInteger, primary_key=True)
    GroupId = Column(BigInteger, nullable=False, index=True)
    RequestId = Column(CHAR(88), nullable=False)
    RequestCreatedAt = Column(DateTime, nullable=False, index=True)
    IsActive = Column(BIT(1), nullable=False)


class JumpTrackGroupKeysTbl(Base):
    __tablename__ = 'JumpTrackGroupKeysTbl'

    GroupId = Column(BigInteger, primary_key=True)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MacSalt = Column(String(44), nullable=False)
    MacKey = Column(String(44), nullable=False)
    MacKeyId = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class JumpTrackGroupPlaneTbl(Base):
    __tablename__ = 'JumpTrackGroupPlaneTbl'

    JumpTrackGroupPlaneTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    GroupId = Column(BigInteger, nullable=False, index=True)
    AddedToGroup = Column(DateTime, nullable=False)
    AcceptedGroup = Column(DateTime)
    IsActive = Column(BIT(1), nullable=False)
    RemovedFromGroup = Column(DateTime)
    AccountId = Column(Integer, nullable=False)


class JumpTrackGroupPositionCheckinsTbl(Base):
    __tablename__ = 'JumpTrackGroupPositionCheckinsTbl'

    JumpTrackGroupPositionCheckinsTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    FromDeviceId = Column(BigInteger, nullable=False)
    GroupId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    Flags = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    GpsAccuracy = Column(Integer, nullable=False)
    TimeOfFix = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackHardwareFailureMessageTbl(Base):
    __tablename__ = 'JumpTrackHardwareFailureMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    AccFailures = Column(Integer, nullable=False)
    IsAccComFailure = Column(BIT(1), nullable=False)
    AltFailures = Column(Integer, nullable=False)
    IsAltComFailure = Column(BIT(1), nullable=False)
    IsAltIntFailure = Column(BIT(1), nullable=False)
    GpsFailures = Column(Integer, nullable=False)
    IsGpsComFailure = Column(BIT(1), nullable=False)
    Sx1262Failures = Column(Integer, nullable=False)
    IsSx1262ComFailure = Column(BIT(1), nullable=False)
    IsSx1262PllFailure = Column(BIT(1), nullable=False)
    IpcFailures = Column(Integer, nullable=False)
    IsIpcComFailure = Column(BIT(1), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackHardwareFailureV2MsgTbl(Base):
    __tablename__ = 'JumpTrackHardwareFailureV2MsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    FailureTime = Column(DateTime, nullable=False)
    AccFailures = Column(Integer, nullable=False)
    IsAccComFailure = Column(BIT(1), nullable=False)
    AltFailures = Column(Integer, nullable=False)
    IsAltComFailure = Column(BIT(1), nullable=False)
    IsAltIntFailure = Column(BIT(1), nullable=False)
    GpsFailures = Column(Integer, nullable=False)
    IsGpsComFailure = Column(BIT(1), nullable=False)
    IsGpsCrystalFailure = Column(BIT(1), nullable=False)
    Sx1262Failures = Column(Integer, nullable=False)
    IsSx1262ComFailure = Column(BIT(1), nullable=False)
    IsSx1262PllFailure = Column(BIT(1), nullable=False)
    IpcFailures = Column(Integer, nullable=False)
    IsIpcComFailure = Column(BIT(1), nullable=False)
    BmsFailures = Column(Integer, nullable=False)
    IsBmsComFailure = Column(BIT(1), nullable=False)
    ExtFlashFailure = Column(Integer, nullable=False)
    IsExtFlashComFailure = Column(BIT(1), nullable=False)
    SecElementFailure = Column(Integer, nullable=False)
    IsSecElementComFailure = Column(BIT(1), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackHipsConfigArchiveTbl(Base):
    __tablename__ = 'JumpTrackHipsConfigArchiveTbl'

    RecordId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False)
    Flags = Column(Integer, nullable=False)
    GroupId = Column(Integer, nullable=False)
    SourceUserId = Column(Integer, nullable=False)
    TimePairedUtc = Column(DateTime, nullable=False)
    TimeUnpairedUtc = Column(DateTime, nullable=False)


class JumpTrackHipsConfigDnlnkTbl(Base):
    __tablename__ = 'JumpTrackHipsConfigDnlnkTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    Flags = Column(Integer, nullable=False)
    GroupId = Column(Integer, nullable=False)
    SourceUserId = Column(Integer, nullable=False)
    TimePairedUtc = Column(DateTime, nullable=False)
    DownlinkMessageId = Column(BigInteger, nullable=False)


class JumpTrackHipsConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackHipsConfigMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfConfig = Column(DateTime, nullable=False)
    Flags = Column(Integer, nullable=False)
    ReportPeriod = Column(Integer, nullable=False)
    ForceCheckin = Column(BIT(1), nullable=False)
    ScanConstantly = Column(BIT(1), nullable=False)
    Mode = Column(Integer, nullable=False)
    GroupCode = Column(Integer, nullable=False)
    SourceUserId = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class JumpTrackHipsSensorDataMsgTbl(Base):
    __tablename__ = 'JumpTrackHipsSensorDataMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfMeasurement = Column(DateTime, nullable=False)
    GroupCode = Column(Integer, nullable=False)
    SourceUserId = Column(Integer, nullable=False)
    HsiDataValue = Column(Float(asdecimal=True), nullable=False)
    HrDataValue = Column(Integer, nullable=False)
    EstimatedCoreTemp = Column(Float(asdecimal=True), nullable=False)
    SkinTemp = Column(Float(asdecimal=True), nullable=False)
    NII = Column(Integer, nullable=False)
    Risk = Column(Integer, nullable=False)
    Confidence = Column(Integer, nullable=False)
    HipsBatteryLife = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class JumpTrackKeysArchiveTbl(Base):
    __tablename__ = 'JumpTrackKeysArchiveTbl'

    Id = Column(Integer, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)
    DateTimeArchivedUtc = Column(DateTime, nullable=False)


class JumpTrackKeysTbl(Base):
    __tablename__ = 'JumpTrackKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)


class JumpTrackLastNonceTbl(Base):
    __tablename__ = 'JumpTrackLastNonceTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    LastNonce = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)


class JumpTrackLoRaBeacon99MessageTbl(Base):
    __tablename__ = 'JumpTrackLoRaBeacon99MessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    TimeOfFix = Column(DateTime, nullable=False)
    GroundSpeed = Column(Integer, nullable=False)
    Heading = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AirPressureInHg = Column(Float(asdecimal=True), nullable=False)
    AltitudeCalculated = Column(Integer, nullable=False)
    BeaconDeviceId = Column(BigInteger, nullable=False, index=True)
    Rssi = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)
    WasReplaced = Column(BIT(1))


class JumpTrackLoRaConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackLoRaConfigDnlnkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    Flags = Column(Integer, nullable=False)
    SessionConfigCrc = Column(Integer, nullable=False)
    DownlinkMessageId = Column(BigInteger, nullable=False)
    AccountId = Column(Integer, nullable=False)


class JumpTrackLoRaConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackLoRaConfigMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfLoRaConfig = Column(DateTime, nullable=False, index=True)
    Flags = Column(Integer, nullable=False)
    SessionConfigCrc = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackLoRaHardwareFailureMessageTbl(Base):
    __tablename__ = 'JumpTrackLoRaHardwareFailureMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    AccFailures = Column(Integer, nullable=False)
    IsAccComFailure = Column(BIT(1), nullable=False)
    AltFailures = Column(Integer, nullable=False)
    IsAltComFailure = Column(BIT(1), nullable=False)
    IsAltIntFailure = Column(BIT(1), nullable=False)
    GpsFailures = Column(Integer, nullable=False)
    IsGpsComFailure = Column(BIT(1), nullable=False)
    Sx1262Failures = Column(Integer, nullable=False)
    IsSx1262ComFailure = Column(BIT(1), nullable=False)
    IsSx1262PllFailure = Column(BIT(1), nullable=False)
    IpcFailures = Column(Integer, nullable=False)
    IsIpcComFailure = Column(BIT(1), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class JumpTrackLoRaKeysArchiveTbl(Base):
    __tablename__ = 'JumpTrackLoRaKeysArchiveTbl'

    Id = Column(Integer, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False)
    AppEui = Column(BigInteger, nullable=False)
    AppSalt = Column(String(44), nullable=False)
    AppKey = Column(String(44), nullable=False)
    AppKeyId = Column(Integer, nullable=False)
    NetSalt = Column(String(44), nullable=False)
    NetKey = Column(String(44), nullable=False)
    NetKeyId = Column(Integer, nullable=False)
    DateTimeArchivedUtc = Column(DateTime, nullable=False)


class JumpTrackLoRaKeysTbl(Base):
    __tablename__ = 'JumpTrackLoRaKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    AppEui = Column(BigInteger, nullable=False)
    AppSalt = Column(String(44), nullable=False)
    AppKey = Column(String(44), nullable=False)
    AppKeyId = Column(Integer, nullable=False)
    NetSalt = Column(String(44), nullable=False)
    NetKey = Column(String(44), nullable=False)
    NetKeyId = Column(Integer, nullable=False)


class JumpTrackLoRaPosition97MessageTbl(Base):
    __tablename__ = 'JumpTrackLoRaPosition97MessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    GroundSpeed = Column(Integer, nullable=False)
    Heading = Column(Integer, nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AirPressureInHg = Column(Float(asdecimal=True), nullable=False)
    AltitudeCalculated = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)
    WasReplaced = Column(BIT(1))


class JumpTrackLoRaPositionMessageTbl(Base):
    __tablename__ = 'JumpTrackLoRaPositionMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AirPressureInHg = Column(Float(asdecimal=True), nullable=False)
    AltitudeCalculated = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class JumpTrackModemConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackModemConfigDnlnkMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    ShortBackoff = Column(Integer, nullable=False)
    NormalBackoff = Column(Integer, nullable=False)
    LongBackoff = Column(Integer, nullable=False)
    RegistrationTimeoutPeriod = Column(Integer, nullable=False)
    SocketConnectionTimeoutPeriod = Column(Integer, nullable=False)
    ConnectionFailureThreshold = Column(Integer, nullable=False)
    SocketTimeoutPeriod = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    DownlinkMessageId = Column(BigInteger, nullable=False, index=True)


class JumpTrackModemConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackModemConfigMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfConfig = Column(DateTime, nullable=False)
    ShortBackoff = Column(Integer, nullable=False)
    NormalBackoff = Column(Integer, nullable=False)
    LongBackoff = Column(Integer, nullable=False)
    RegistrationTimeoutPeriod = Column(Integer, nullable=False)
    SocketConnectionTimeoutPeriod = Column(Integer, nullable=False)
    ConnectionFailureThreshold = Column(Integer, nullable=False)
    SocketTimeoutPeriod = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class JumpTrackPositionMessageTbl(Base):
    __tablename__ = 'JumpTrackPositionMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AltitudeGps = Column(Integer, nullable=False)
    BatteryVoltage = Column(Integer)
    TimeOfFix = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackPositionV2MessageTbl(Base):
    __tablename__ = 'JumpTrackPositionV2MessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AltitudeGps = Column(Integer, nullable=False)
    GroundSpeed = Column(Integer, nullable=False)
    Heading = Column(Integer, nullable=False)
    BatteryVoltage = Column(Integer, nullable=False)
    TimeOfFix = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)
    WasReplaced = Column(BIT(1))


class JumpTrackRebootMsgTbl(Base):
    __tablename__ = 'JumpTrackRebootMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    RebootPattern = Column(Integer, nullable=False)
    RebootFlags = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackSensorMessageTbl(Base):
    __tablename__ = 'JumpTrackSensorMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    AirPressureInHg = Column(Float(asdecimal=True), nullable=False)
    Temperature = Column(Float(asdecimal=True), nullable=False)
    AltitudeCalculated = Column(Integer, nullable=False)
    TimeOfMeasurement = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackSensorV2MessageTbl(Base):
    __tablename__ = 'JumpTrackSensorV2MessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    AirPressureInHg = Column(Float(asdecimal=True), nullable=False)
    Temperature = Column(Float(asdecimal=True), nullable=False)
    AverageForce = Column(Float(asdecimal=True), nullable=False)
    MaxForce = Column(Float(asdecimal=True), nullable=False)
    AltitudeCalculated = Column(Integer, nullable=False)
    TimeOfMeasurement = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)


class JumpTrackServerConfigDnlnkTbl(Base):
    __tablename__ = 'JumpTrackServerConfigDnlnkTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    Flags = Column(Integer, nullable=False)
    Port = Column(Integer, nullable=False)
    ServerUrl = Column(String(132))
    DownlinkMessageId = Column(BigInteger, nullable=False)


class JumpTrackServerConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackServerConfigMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    Port = Column(Integer, nullable=False)
    ServerUrl = Column(String(132))
    AccountId = Column(Integer, nullable=False)


class JumpTrackSimConfigDnlnkTbl(Base):
    __tablename__ = 'JumpTrackSimConfigDnlnkTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    Flags = Column(Integer, nullable=False)
    DownlinkMessageId = Column(BigInteger, nullable=False)


class JumpTrackSimConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackSimConfigMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeOfConfig = Column(DateTime, nullable=False)
    Flags = Column(Integer, nullable=False)
    DefaultSimSelect = Column(BIT(1), nullable=False)
    AccountId = Column(Integer, nullable=False)


class KudelskiDecryptionResultTbl(Base):
    __tablename__ = 'KudelskiDecryptionResultTbl'

    KudelskiDecryptionResultTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False)
    RotPublicUid = Column(BigInteger, nullable=False)
    NumberAttempts = Column(Integer)
    HttpResponse = Column(Integer, nullable=False)
    CheckInId = Column(BigInteger, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)
    MessageTypeId = Column(Integer, nullable=False)
    LastEventTime = Column(DateTime, nullable=False)
    TimeToDecrypt = Column(BigInteger)
    DecryptionSuccess = Column(BIT(1), nullable=False)
    ErrorMessage = Column(String(256))
    AccountId = Column(Integer, nullable=False)


class LastLocationTbl(Base):
    __tablename__ = 'LastLocationTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    LocationId = Column(BigInteger, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False)
    WasManualAssignment = Column(BIT(1), nullable=False)
    LastCheckin = Column(DateTime, nullable=False, index=True)
    BatteryVoltage = Column(Float(asdecimal=True))
    LastPosition = Column(DateTime)
    PositionLocationId = Column(Integer)
    LastFw = Column(DateTime)
    BlVersion = Column(Integer)
    FwVersion = Column(Integer)
    FwLocationId = Column(Integer)
    AccountId = Column(Integer, nullable=False, index=True)


class LoRaDownlinkEnableListTbl(Base):
    __tablename__ = 'LoRaDownlinkEnableListTbl'

    LoRaDownlinkEnableListTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    LoRaDownlinkEnableList = Column(BigInteger, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class LoRaDownlinkLocationMapTbl(Base):
    __tablename__ = 'LoRaDownlinkLocationMapTbl'

    LoRaDownlinkLocationMapTblId = Column(BigInteger, primary_key=True)
    LoRaDownlinkTblId = Column(BigInteger, nullable=False, index=True)
    LocationId = Column(BigInteger, nullable=False, index=True)
    IsActive = Column(BIT(1), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class LoRaDownlinkTbl(Base):
    __tablename__ = 'LoRaDownlinkTbl'

    LoRaDownlinkTblId = Column(BigInteger, primary_key=True)
    Port = Column(Integer, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    MessageCompare = Column(String(345), nullable=False)
    MessageCompareMask = Column(String(345))
    SendIfMatch = Column(BIT(1), nullable=False)
    SendPort = Column(Integer)
    SendMessage = Column(String(345))
    SendConfirmed = Column(BIT(1), nullable=False)
    LoRaDownlinkEnableList = Column(BigInteger, index=True)
    IsActive = Column(BIT(1), nullable=False)
    IsAllDevices = Column(BIT(1), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    NandMaskB64 = Column(String(345))


class LoRaDownlinksArchiveTbl(Base):
    __tablename__ = 'LoRaDownlinksArchiveTbl'

    ArchiveId = Column(BigInteger, primary_key=True)
    Description = Column(String(64), nullable=False)
    AccountId = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)
    UplinkPort = Column(Integer, nullable=False)
    UplinkMsgB64 = Column(String(345), nullable=False)
    AndMaskB64 = Column(String(345))
    NandMaskB64 = Column(String(345))
    DownlinkPort = Column(Integer, nullable=False)
    DownlinkMsgB64 = Column(String(345), nullable=False)
    MulticastGroupId = Column(BigInteger)
    SendConfirmed = Column(BIT(1), nullable=False)
    SendToAll = Column(BIT(1), nullable=False)
    SendToLocations = Column(BIT(1), nullable=False)
    SendToDevices = Column(BIT(1), nullable=False)
    TimeConfiguredUtc = Column(DateTime, nullable=False)
    TimeArchivedUtc = Column(DateTime, nullable=False)


class LoRaDownlinksDeviceMapArchiveTbl(Base):
    __tablename__ = 'LoRaDownlinksDeviceMapArchiveTbl'

    Id = Column(BigInteger, primary_key=True)
    LoRaDownlinksTblId = Column(BigInteger, nullable=False)
    DeviceId = Column(BigInteger, nullable=False)


class LoRaDownlinksDeviceMapTbl(Base):
    __tablename__ = 'LoRaDownlinksDeviceMapTbl'

    Id = Column(BigInteger, primary_key=True)
    LoRaDownlinksTblId = Column(BigInteger, nullable=False, index=True)
    DeviceId = Column(BigInteger, nullable=False)


class LoRaDownlinksLocationMapArchiveTbl(Base):
    __tablename__ = 'LoRaDownlinksLocationMapArchiveTbl'

    Id = Column(BigInteger, primary_key=True)
    LoRaDownlinksTblId = Column(BigInteger, nullable=False)
    LocationId = Column(BigInteger, nullable=False)


class LoRaDownlinksLocationMapTbl(Base):
    __tablename__ = 'LoRaDownlinksLocationMapTbl'

    Id = Column(BigInteger, primary_key=True)
    LoRaDownlinksTblId = Column(BigInteger, nullable=False, index=True)
    LocationId = Column(BigInteger, nullable=False)


class LoRaDownlinksTbl(Base):
    __tablename__ = 'LoRaDownlinksTbl'

    LoRaDownlinksTblId = Column(BigInteger, primary_key=True)
    Description = Column(String(64), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    UplinkPort = Column(Integer, nullable=False, index=True)
    UplinkMsgB64 = Column(String(345), nullable=False)
    AndMaskB64 = Column(String(345))
    NandMaskB64 = Column(String(345))
    DownlinkPort = Column(Integer, nullable=False)
    DownlinkMsgB64 = Column(String(345), nullable=False)
    MulticastGroupId = Column(BigInteger, index=True)
    SendConfirmed = Column(BIT(1), nullable=False)
    SendToAll = Column(BIT(1), nullable=False)
    SendToLocations = Column(BIT(1), nullable=False)
    SendToDevices = Column(BIT(1), nullable=False)
    TimeConfiguredUtc = Column(DateTime, nullable=False)


class LoRaFailMessageTbl(Base):
    __tablename__ = 'LoRaFailMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    FailureReason = Column(Integer, nullable=False)
    Port = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)
    Message = Column(String(345))
    AccountId = Column(Integer, nullable=False)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class LoRaGatewayLocationMapTbl(Base):
    __tablename__ = 'LoRaGatewayLocationMapTbl'

    LoRaGatewayLocationMapTbl = Column(BigInteger, primary_key=True)
    LocationId = Column(BigInteger, nullable=False, index=True)
    LoRaGatewayId = Column(Integer, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)


class LoRaLocEstTbl(Base):
    __tablename__ = 'LoRaLocEstTbl'

    LoRaLocEstTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeRx = Column(DateTime, nullable=False, index=True)
    Lat = Column(Float(asdecimal=True), nullable=False)
    Lon = Column(Float(asdecimal=True), nullable=False)
    Alt = Column(Float(asdecimal=True), nullable=False)
    HDop = Column(Float(asdecimal=True), nullable=False, index=True)
    GDop = Column(Float(asdecimal=True), nullable=False)
    NumUlPacketsUsed = Column(Integer, nullable=False)
    NumGatewaysUsed = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class LoRaMulticastGatewayMapArchiveTbl(Base):
    __tablename__ = 'LoRaMulticastGatewayMapArchiveTbl'

    ArchiveId = Column(BigInteger, primary_key=True)
    MulticastGroupDeviceId = Column(BigInteger, nullable=False, index=True)
    LoRaGatewayId = Column(Integer, nullable=False)
    TimePairedUtc = Column(DateTime, nullable=False)
    TimeArchivedUtc = Column(DateTime, nullable=False)


class LoRaMulticastGatewayMapTbl(Base):
    __tablename__ = 'LoRaMulticastGatewayMapTbl'

    MapId = Column(BigInteger, primary_key=True)
    MulticastGroupDeviceId = Column(BigInteger, nullable=False, index=True)
    LoRaGatewayId = Column(Integer, nullable=False, index=True)
    TimePairedUtc = Column(DateTime, nullable=False)


class LoRaMulticastGroupsArchiveTbl(Base):
    __tablename__ = 'LoRaMulticastGroupsArchiveTbl'

    ArchiveTblId = Column(BigInteger, primary_key=True)
    LoRaNetworkId = Column(BigInteger, nullable=False)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    DeviceAddress = Column(Integer, nullable=False)
    GroupName = Column(String(48), nullable=False)
    GroupType = Column(String(1), nullable=False)
    FCount = Column(BigInteger, nullable=False)
    DataRate = Column(BigInteger, nullable=False)
    Frequency = Column(BigInteger, nullable=False)
    PingSlotPeriod = Column(BigInteger, nullable=False)
    TimeAddedToNetworkUtc = Column(DateTime, nullable=False)
    TimeArchivedUtc = Column(DateTime, nullable=False, index=True)


class LoRaMulticastGroupsTbl(Base):
    __tablename__ = 'LoRaMulticastGroupsTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    LoRaNetworkId = Column(BigInteger, nullable=False)
    DeviceAddress = Column(Integer, nullable=False)
    GroupName = Column(String(48), nullable=False)
    GroupType = Column(String(1), nullable=False)
    FCount = Column(BigInteger, nullable=False)
    DataRate = Column(BigInteger, nullable=False)
    Frequency = Column(BigInteger, nullable=False)
    PingSlotPeriod = Column(BigInteger, nullable=False)
    TimeAddedToNetworkUtc = Column(DateTime, nullable=False)


class LoRaMulticastKeysArchiveTbl(Base):
    __tablename__ = 'LoRaMulticastKeysArchiveTbl'

    KeysArchiveTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False)
    AppSalt = Column(String(44), nullable=False)
    AppHash = Column(String(44), nullable=False)
    AppKeyId = Column(Integer, nullable=False)
    NetSalt = Column(String(44), nullable=False)
    NetHash = Column(String(44), nullable=False)
    NetKeyId = Column(Integer, nullable=False)
    TimeArchivedUtc = Column(DateTime, nullable=False, index=True)


class LoRaMulticastKeysTbl(Base):
    __tablename__ = 'LoRaMulticastKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    AppSalt = Column(String(44), nullable=False)
    AppHash = Column(String(44), nullable=False)
    AppKeyId = Column(Integer, nullable=False)
    NetSalt = Column(String(44), nullable=False)
    NetHash = Column(String(44), nullable=False)
    NetKeyId = Column(Integer, nullable=False)


class LoRaMulticastTypeTbl(Base):
    __tablename__ = 'LoRaMulticastTypeTbl'

    LoRaMulticastTypeId = Column(Integer, primary_key=True)
    LoRaMulticastTypeName = Column(String(64), nullable=False)


class LoRaMulticastsArchiveTbl(Base):
    __tablename__ = 'LoRaMulticastsArchiveTbl'

    LoRaMulticastArchiveTblId = Column(BigInteger, primary_key=True)
    MulticastGroupDeviceId = Column(BigInteger, nullable=False)
    LoRaMulticastTypeId = Column(Integer, nullable=False)
    Description = Column(String(64), nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)
    DownlinkPort = Column(Integer, nullable=False)
    TxPeriodSec = Column(Integer, nullable=False)
    TxOffsetSec = Column(Integer, nullable=False)
    RxWindowSec = Column(Integer, nullable=False)
    ScanPeriodMin = Column(Integer, nullable=False)
    CallbackUtilityName = Column(String(64), nullable=False)
    CallbackUrlPath = Column(String(64), nullable=False)
    StringCol1 = Column(String(64))
    StringCol2 = Column(String(64))
    StringCol3 = Column(String(64))
    IntCol1 = Column(Integer)
    IntCol2 = Column(Integer)
    IntCol3 = Column(Integer)
    DoubleCol1 = Column(Float(asdecimal=True))
    DoubleCol2 = Column(Float(asdecimal=True))
    DoubleCol3 = Column(Float(asdecimal=True))
    TimeConfiguredUtc = Column(DateTime, nullable=False)
    TimeArchivedUtc = Column(DateTime, nullable=False)


class LoRaMulticastsTbl(Base):
    __tablename__ = 'LoRaMulticastsTbl'

    MulticastGroupDeviceId = Column(BigInteger, primary_key=True)
    LoRaMulticastTypeId = Column(Integer, nullable=False)
    Description = Column(String(64), nullable=False)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    DownlinkPort = Column(Integer, nullable=False)
    TxPeriodSec = Column(Integer, nullable=False)
    TxOffsetSec = Column(Integer, nullable=False)
    RxWindowSec = Column(Integer, nullable=False)
    ScanPeriodMin = Column(Integer, nullable=False)
    CallbackUtilityName = Column(String(64), nullable=False)
    CallbackUrlPath = Column(String(64), nullable=False)
    StringCol1 = Column(String(64))
    StringCol2 = Column(String(64))
    StringCol3 = Column(String(64))
    IntCol1 = Column(Integer)
    IntCol2 = Column(Integer)
    IntCol3 = Column(Integer)
    DoubleCol1 = Column(Float(asdecimal=True))
    DoubleCol2 = Column(Float(asdecimal=True))
    DoubleCol3 = Column(Float(asdecimal=True))
    TimeConfiguredUtc = Column(DateTime, nullable=False)


class LoRaNetAccountMapArchiveTbl(Base):
    __tablename__ = 'LoRaNetAccountMapArchiveTbl'

    ArchiveId = Column(BigInteger, primary_key=True)
    LoRaNetworkId = Column(BigInteger, nullable=False)
    UserAccountId = Column(Integer, nullable=False)
    TimeAssociatedUtc = Column(DateTime, nullable=False)
    TimeArchivedUtc = Column(DateTime, nullable=False)


class LoRaNetAccountMapTbl(Base):
    __tablename__ = 'LoRaNetAccountMapTbl'

    LoRaNetAccountMapTblId = Column(BigInteger, primary_key=True)
    LoRaNetworkId = Column(BigInteger, nullable=False)
    UserAccountId = Column(Integer, nullable=False, index=True)
    TimeAssociatedUtc = Column(DateTime, nullable=False)


class LoRaNetDevMapArchiveTbl(Base):
    __tablename__ = 'LoRaNetDevMapArchiveTbl'

    LoRaNetDevMapArchiveTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    LoRaNetworkId = Column(BigInteger, nullable=False)
    TimeAddedToNetworkUtc = Column(DateTime, nullable=False)
    TimeArchivedUtc = Column(DateTime, nullable=False, index=True)


class LoRaNetDevMapTbl(Base):
    __tablename__ = 'LoRaNetDevMapTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    LoRaNetworkId = Column(BigInteger, nullable=False, index=True)
    TimeAddedToNetworkUtc = Column(DateTime, nullable=False)


class LoRaNetworkGatewayTbl(Base):
    __tablename__ = 'LoRaNetworkGatewayTbl'

    LoRaGatewayId = Column(Integer, primary_key=True)
    LoRaNetworkId = Column(BigInteger, nullable=False)
    NetworkTypeId = Column(Integer, nullable=False)
    IdentifierToNetwork = Column(String(16), nullable=False)
    GatewayName = Column(String(32), nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Altitude = Column(Float(asdecimal=True), nullable=False)
    GatewayCheckinId = Column(String(32), nullable=False)
    GatewayNodeId = Column(String(45))
    AccountId = Column(Integer, nullable=False)


class LoRaNetworkTbl(Base):
    __tablename__ = 'LoRaNetworkTbl'

    LoRaNetworkId = Column(BigInteger, primary_key=True)
    NetworkTypeId = Column(Integer, nullable=False)
    Description = Column(String(64), nullable=False)
    TimeCreatedUtc = Column(DateTime, nullable=False)
    OwnerAccountId = Column(Integer, nullable=False)
    EndpointId = Column(BigInteger, nullable=False)
    IsActive = Column(BIT(1), nullable=False)
    TimeDeactivatedUtc = Column(DateTime)


class LoRaNetworkTypeTbl(Base):
    __tablename__ = 'LoRaNetworkTypeTbl'

    NetworkTypeId = Column(Integer, primary_key=True)
    NetworkTypeName = Column(String(48))


class LoRaSentMsgTbl(Base):
    __tablename__ = 'LoRaSentMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeSent = Column(DateTime, nullable=False, index=True)
    Port = Column(Integer, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    SentMessage = Column(String(345))
    LoRaNetworkId = Column(BigInteger)
    AccountId = Column(Integer, nullable=False)


class LoRaToaDataArchiveTbl(Base):
    __tablename__ = 'LoRaToaDataArchiveTbl'

    LoRaToaDataTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeRx = Column(DateTime, nullable=False, index=True)
    DevAddr = Column(Integer, nullable=False)
    FrameCnt = Column(Integer, nullable=False)
    FreqHz = Column(Integer, nullable=False)
    BwHz = Column(Integer, nullable=False)
    Sf = Column(Integer, nullable=False)
    Rssi = Column(Integer, nullable=False)
    Snr = Column(Float(asdecimal=True), nullable=False)
    ToaSec = Column(Integer, nullable=False)
    ToaNsec = Column(Integer, nullable=False)
    FoHz = Column(Integer, nullable=False)
    ToaUNsec = Column(Integer, nullable=False)
    FoUHz = Column(Integer, nullable=False)
    GwId = Column(BigInteger, nullable=False, index=True)
    AntInd = Column(Integer, nullable=False)
    AntLat = Column(Float(asdecimal=True), nullable=False)
    AntLon = Column(Float(asdecimal=True), nullable=False)
    AntAlt = Column(Float(asdecimal=True), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class LoRaToaDataTbl(Base):
    __tablename__ = 'LoRaToaDataTbl'

    LoRaToaDataTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeRx = Column(DateTime, nullable=False, index=True)
    DevAddr = Column(Integer, nullable=False)
    FrameCnt = Column(Integer, nullable=False)
    FreqHz = Column(Integer, nullable=False)
    BwHz = Column(Integer, nullable=False)
    Sf = Column(Integer, nullable=False)
    Rssi = Column(Integer, nullable=False)
    Snr = Column(Float(asdecimal=True), nullable=False)
    ToaSec = Column(Integer, nullable=False)
    ToaNsec = Column(Integer, nullable=False)
    FoHz = Column(Integer, nullable=False)
    ToaUNsec = Column(Integer, nullable=False)
    FoUHz = Column(Integer, nullable=False)
    GwId = Column(BigInteger, nullable=False, index=True)
    AntInd = Column(Integer, nullable=False)
    AntLat = Column(Float(asdecimal=True), nullable=False)
    AntLon = Column(Float(asdecimal=True), nullable=False)
    AntAlt = Column(Float(asdecimal=True), nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class LocationReportDataTbl(Base):
    __tablename__ = 'LocationReportDataTbl'

    LocationReportDataTblId = Column(BigInteger, primary_key=True)
    LocationReportId = Column(BigInteger, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    ParamName = Column(String(32), nullable=False)
    ParamValue = Column(Float(asdecimal=True))
    Count = Column(Integer)
    RangeMin = Column(Float(asdecimal=True))
    RangeMax = Column(Float(asdecimal=True))
    ShouldDisplay = Column(BIT(1), nullable=False)


class LocationReportTbl(Base):
    __tablename__ = 'LocationReportTbl'

    LocationReportId = Column(BigInteger, primary_key=True)
    LocationId = Column(BigInteger, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    ReportGenerated = Column(DateTime, nullable=False, index=True)
    DeviceCount = Column(Integer, nullable=False)
    TotalCheckedIn = Column(Integer, nullable=False)
    TotalCheckedInWithin24 = Column(Integer)


class LocationTbl(Base):
    __tablename__ = 'LocationTbl'

    LocationId = Column(BigInteger, primary_key=True)
    LocationName = Column(String(32), nullable=False)
    Latitude = Column(Float(asdecimal=True))
    Longitude = Column(Float(asdecimal=True))
    AccountId = Column(Integer, nullable=False, index=True)


class MachineqAddToResultTbl(Base):
    __tablename__ = 'MachineqAddToResultTbl'

    MachineqAddToResultTblId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeAttempted = Column(DateTime, nullable=False)
    AddedSuccessfully = Column(BIT(1), nullable=False)
    TimeToAdd = Column(BigInteger, nullable=False)
    HttpResponseCode = Column(Integer, nullable=False)


class MachineqNetworkParamsTbl(Base):
    __tablename__ = 'MachineqNetworkParamsTbl'

    MachineqNetworkParamsTbl = Column(BigInteger, primary_key=True)
    LoRaNetworkId = Column(BigInteger, nullable=False, index=True)
    DeviceProfile = Column(String(32), nullable=False)
    ServiceProfile = Column(String(32), nullable=False)
    OutputProfile = Column(String(32), nullable=False)


class MopTrackCheckinsTbl(Base):
    __tablename__ = 'MopTrackCheckinsTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    Rssi = Column(Integer, nullable=False)
    EncryptedData = Column(String(5464), nullable=False)
    AccountId = Column(Integer, nullable=False)
    GatewayId = Column(BigInteger, nullable=False)
    DataSource = Column(Integer)
    Latitude = Column(Float(asdecimal=True))
    Longitude = Column(Float(asdecimal=True))


class NetSocketNetworkStatusMessageTbl(Base):
    __tablename__ = 'NetSocketNetworkStatusMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    LteConnected = Column(BIT(1), nullable=False)
    SocketConnected = Column(BIT(1), nullable=False)
    SendSuccess = Column(BIT(1), nullable=False)
    WirelessTechnology = Column(BIT(1))
    ActiveSimSlot = Column(BIT(1))
    EarlySocketDisconnect = Column(BIT(1))
    DnssecResolved = Column(BIT(1))
    TimeSpent = Column(Integer, nullable=False)
    TimeOfConnection = Column(DateTime, nullable=False)
    RSRQ = Column(Float(asdecimal=True), nullable=False)
    RSRP = Column(Float(asdecimal=True), nullable=False)
    NumberOfBytesSent = Column(Integer, nullable=False)
    NumberOfBytesReceived = Column(Integer, nullable=False)
    Band = Column(Integer)
    EnergyEstimate = Column(Integer)
    NetworkId = Column(Integer)
    AccountId = Column(Integer, nullable=False, index=True)


class NurBeaconScanMsgTbl(Base):
    __tablename__ = 'NurBeaconScanMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    ScanEvent = Column(Integer, nullable=False, index=True)
    BeaconId = Column(BigInteger, nullable=False)
    AvgRssi = Column(Integer, nullable=False)
    NumRx = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime, index=True)


class NurBleBeaconConfigMsgTbl(Base):
    __tablename__ = 'NurBleBeaconConfigMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    BeaconPeriod = Column(Integer, nullable=False)
    BeaconDuration = Column(Integer, nullable=False)
    BeaconPower = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class NurBleConfigMsgTbl(Base):
    __tablename__ = 'NurBleConfigMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    BeaconScanDuration = Column(Integer, nullable=False)
    MaxSatLocTime = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    IsEarlyIndoorEn = Column(BIT(1), nullable=False)
    IsEarlyIndoorAlwaysEn = Column(BIT(1), nullable=False)
    MinNumSat = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class NurBootMessageTbl(Base):
    __tablename__ = 'NurBootMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    ExceptionVector = Column(Integer, nullable=False)
    BootReason = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurCatBootMessageTbl(Base):
    __tablename__ = 'NurCatBootMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    BootReason = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class NurCatFirmwareMessageTbl(Base):
    __tablename__ = 'NurCatFirmwareMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    BootloaderVersion = Column(Integer, nullable=False)
    ApplicationVersion = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class NurCatKeysTbl(Base):
    __tablename__ = 'NurCatKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)


class NurCatLastNonceTbl(Base):
    __tablename__ = 'NurCatLastNonceTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    LastNonce = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)


class NurCatPositionMessageTbl(Base):
    __tablename__ = 'NurCatPositionMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AltitudeGps = Column(Integer, nullable=False)
    BatteryVoltage = Column(Integer, nullable=False)
    TimeOfFix = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)


class NurConfigurationMessageTbl(Base):
    __tablename__ = 'NurConfigurationMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    AccThresh = Column(Integer, nullable=False)
    AccDur = Column(Integer, nullable=False)
    StopMotionWait = Column(Integer, nullable=False)
    HeartBeat = Column(Integer, nullable=False)
    GpsTtf = Column(Integer, nullable=False)
    ContMotionWait = Column(Integer, nullable=False)
    AccThreshDis = Column(Integer, nullable=False)
    AccDurDis = Column(Integer, nullable=False)
    StopMotionWaitDis = Column(Integer, nullable=False)
    AccSettings = Column(Integer, nullable=False)
    AccPoll = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurFirmwareMessageTbl(Base):
    __tablename__ = 'NurFirmwareMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DATETIME(fsp=3), nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    FirmwareVersion = Column(Integer, nullable=False)
    BootloaderVersion = Column(Integer, nullable=False)
    FuotaVersion = Column(Integer, nullable=False)
    NumberReceivedFuotaPackets = Column(Integer, nullable=False)
    MulticastConfigCrc = Column(Integer)
    AccountId = Column(Integer, nullable=False)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurHardwareFailuresMessageTbl(Base):
    __tablename__ = 'NurHardwareFailuresMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    GpsFailures = Column(Integer, nullable=False)
    AccelerometerFailures = Column(Integer, nullable=False)
    ExternalFlashFailures = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurIndoorLocConfigMsgTbl(Base):
    __tablename__ = 'NurIndoorLocConfigMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NumberOfSends = Column(Integer, nullable=False)
    TimeBetweenSends = Column(Integer, nullable=False)
    MaxTimeSatLock = Column(Integer, nullable=False)
    IsEarlyIndoorEn = Column(BIT(1), nullable=False)
    IsEarlyIndoorAlwaysEn = Column(BIT(1), nullable=False)
    MinNumSat = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurIndoorLocMsgTbl(Base):
    __tablename__ = 'NurIndoorLocMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    EventNum = Column(Integer, nullable=False, index=True)
    PacketCounter = Column(Integer, nullable=False)
    IsFinal = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    DevAddr = Column(Integer, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurIndoorLocV2MsgTbl(Base):
    __tablename__ = 'NurIndoorLocV2MsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    ScanEvent = Column(Integer, nullable=False, index=True)
    NumberOfBeacons = Column(Integer, nullable=False)
    ScanTime = Column(Integer, nullable=False)
    Battery = Column(Integer, nullable=False)
    Temperature = Column(Float(asdecimal=True), nullable=False)
    TimeInMotion = Column(Integer, nullable=False)
    Crc = Column(Integer, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime, index=True)


class NurJumpTrack95MessageTbl(Base):
    __tablename__ = 'NurJumpTrack95MessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    AltitudeGps = Column(Integer, nullable=False)
    BatteryVoltage = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurKeysArchiveTbl(Base):
    __tablename__ = 'NurKeysArchiveTbl'

    NurKeysArchiveTblId = Column(Integer, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    AppEui = Column(BigInteger, nullable=False)
    AppSalt = Column(String(44), nullable=False)
    AppKey = Column(String(44), nullable=False)
    AppKeyId = Column(Integer, nullable=False)
    NetSalt = Column(String(44), nullable=False)
    NetKey = Column(String(44), nullable=False)
    NetKeyId = Column(Integer, nullable=False)
    DateTimeArchivedUtc = Column(DateTime, nullable=False)


class NurKeysTbl(Base):
    __tablename__ = 'NurKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    AppSalt = Column(String(44), nullable=False)
    AppKey = Column(String(44), nullable=False)
    AppKeyId = Column(Integer, nullable=False)
    NetSalt = Column(String(44), nullable=False)
    NetKey = Column(String(44), nullable=False)
    NetKeyId = Column(Integer, nullable=False)
    AppEui = Column(BigInteger, nullable=False)


class NurPositionMessageTbl(Base):
    __tablename__ = 'NurPositionMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    State = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    Battery = Column(Integer, nullable=False)
    IsAssociated = Column(BIT(1), nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsIndoor = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurPositionV2MsgTbl(Base):
    __tablename__ = 'NurPositionV2MsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    TimeOfFix = Column(DateTime, nullable=False, index=True)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    Battery = Column(Integer, nullable=False)
    IsAssociated = Column(BIT(1), nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    IsUsingGpsAiding = Column(BIT(1), nullable=False)
    Temperature = Column(Float(asdecimal=True), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    TimeInMotion = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)
    Crc = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class NurStartMotionCnfgMsgTbl(Base):
    __tablename__ = 'NurStartMotionCnfgMsgTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    StartMotionWindowStart = Column(Integer, nullable=False)
    StartMotionWindowEnd = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False, index=True)


class NurStartMotionMsgTbl(Base):
    __tablename__ = 'NurStartMotionMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    MultiCrc = Column(Integer)
    AccountId = Column(Integer, nullable=False, index=True)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class PositionMessageTankTrackTbl(Base):
    __tablename__ = 'PositionMessageTankTrackTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Flags = Column(Integer, nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsGpsIndoors = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    TimeOfFix = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False)


class PowerINA219MessageICLETbl(Base):
    __tablename__ = 'PowerINA219MessageICLETbl'

    CheckInId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DATETIME(fsp=3), nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Nonce = Column(Integer, nullable=False)
    PowerPort = Column(Integer, nullable=False)
    TimeOfFirstMeasurement = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    BusVoltage = Column(Float, nullable=False)
    ShuntVoltage = Column(Float, nullable=False)
    NumberOfSamples = Column(Integer, nullable=False)
    Ina219Config = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class RatFuckTbl(Base):
    __tablename__ = 'RatFuckTbl'

    RatFuckId = Column(BigInteger, primary_key=True)
    RatFuck = Column(String(32), nullable=False)


class RelayMessageICLETbl(Base):
    __tablename__ = 'RelayMessageICLETbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DATETIME(fsp=3), nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    RelayPort = Column(Integer, nullable=False)
    TimeActuated = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    EventDuration = Column(Integer, nullable=False)
    ActuationType = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class ScratchPadMsgTbl(Base):
    __tablename__ = 'ScratchPadMsgTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    MsgPayload = Column(String(771))
    AccountId = Column(Integer, nullable=False)


class StartMotionMessageTankTrackTbl(Base):
    __tablename__ = 'StartMotionMessageTankTrackTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    AccThresh = Column(Integer, nullable=False)
    AccDur = Column(Integer, nullable=False)
    TimeOfMovement = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False)


class SystemEndpointsMapTbl(Base):
    __tablename__ = 'SystemEndpointsMapTbl'

    SystemEndpointMapId = Column(Integer, primary_key=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False, index=True)
    EndpointId = Column(BigInteger, nullable=False)
    IsActive = Column(BIT(1), nullable=False)


class TankLevelMessageTankTrackTbl(Base):
    __tablename__ = 'TankLevelMessageTankTrackTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    Tank1Level = Column(Integer, nullable=False)
    Tank1Alarm = Column(Integer, nullable=False)
    Tank2Level = Column(Integer, nullable=False)
    Tank2Alarm = Column(Integer, nullable=False)
    BatteryVoltage = Column(Integer, nullable=False)
    TimeOfMeasurement = Column(DateTime, nullable=False, index=True)
    AccountId = Column(Integer, nullable=False)


class TankTrackKeysTbl(Base):
    __tablename__ = 'TankTrackKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)


class TankTrackLastNonceTbl(Base):
    __tablename__ = 'TankTrackLastNonceTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    LastNonce = Column(Integer, nullable=False)
    DeviceTypeId = Column(Integer, nullable=False)


class TestDevicePositionMessageTbl(Base):
    __tablename__ = 'TestDevicePositionMessageTbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    State = Column(Integer, nullable=False)
    Latitude = Column(Float(asdecimal=True), nullable=False)
    Longitude = Column(Float(asdecimal=True), nullable=False)
    Ttf = Column(Integer, nullable=False)
    Accuracy = Column(Integer, nullable=False)
    Battery = Column(Integer, nullable=False)
    IsAssociated = Column(BIT(1), nullable=False)
    IsValidGpsFix = Column(BIT(1), nullable=False)
    IsIndoor = Column(BIT(1), nullable=False)
    IsInMotion = Column(BIT(1), nullable=False)
    UpdateReason = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)
    FCntUp = Column(Integer)
    FCntDn = Column(Integer)
    GatewayLat = Column(Float(asdecimal=True))
    GatewayLon = Column(Float(asdecimal=True))
    GatewayId = Column(String(16))
    GatewayCount = Column(Integer)
    GatewayRssi = Column(Float(asdecimal=True))
    GatewaySnr = Column(Float(asdecimal=True))
    Channel = Column(String(4))
    SpreadingFactor = Column(Integer)
    NetworkTimeReceived = Column(DateTime)


class TimeRequestIdentifierTbl(Base):
    __tablename__ = 'TimeRequestIdentifierTbl'

    DeviceId = Column(BigInteger, primary_key=True, unique=True)
    DeviceTypeId = Column(Integer, nullable=False, index=True)


class TimeRequestMessageTbl(Base):
    __tablename__ = 'TimeRequestMessageTbl'

    TimeRequestMessageId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DATETIME(fsp=3), nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeRequestId = Column(BigInteger, nullable=False)
    TimeSinceBoot = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class TimeResponseMessageTbl(Base):
    __tablename__ = 'TimeResponseMessageTbl'

    TimeResponseMessageId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DATETIME(fsp=3), nullable=False)
    FromDevice = Column(BIT(1), nullable=False)
    NonceReceived = Column(Integer, nullable=False)
    TimeResponse = Column(DATETIME(fsp=3), nullable=False)
    AccountId = Column(Integer, nullable=False)


class Track02Tbl(Base):
    __tablename__ = 'Track02Tbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    DeviceIdentifier = Column(BigInteger, nullable=False)
    TimeSinceBoot = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class Track04Tbl(Base):
    __tablename__ = 'Track04Tbl'

    CheckinId = Column(BigInteger, primary_key=True)
    DeviceId = Column(BigInteger, nullable=False, index=True)
    TimeReceived = Column(DateTime, nullable=False, index=True)
    FromDevice = Column(BIT(1), nullable=False)
    Flags = Column(Integer, nullable=False)
    FirmwareVersion = Column(Integer, nullable=False)
    AccountId = Column(Integer, nullable=False)


class TrackKeysTbl(Base):
    __tablename__ = 'TrackKeysTbl'

    DeviceId = Column(BigInteger, primary_key=True)
    EncSalt = Column(String(44), nullable=False)
    EncKey = Column(String(44), nullable=False)
    EncKeyId = Column(Integer, nullable=False)
    MicSalt = Column(String(44), nullable=False)
    MicKey = Column(String(44), nullable=False)
    MicKeyId = Column(Integer, nullable=False)


class UtilityEndpointsTbl(Base):
    __tablename__ = 'UtilityEndpointsTbl'

    UtilityEndpointTblId = Column(Integer, primary_key=True)
    UtilityName = Column(String(64), nullable=False)
    EndpointId = Column(BigInteger, nullable=False)

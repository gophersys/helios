from typing import Any, Optional
import datetime
import decimal

from sqlalchemy import BigInteger, CHAR, DateTime, Double, Float, Index, Integer, String, TIMESTAMP, text
from sqlalchemy.dialects.mysql import BIT, DATETIME
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class AccountTypesTbl(Base):
    __tablename__ = 'AccountTypesTbl'
    __table_args__ = (
        Index('AccountTypeId_UNIQUE', 'AccountTypeId', unique=True),
    )

    AccountTypeId: Mapped[int] = mapped_column(Integer, primary_key=True)
    AccountTypeName: Mapped[str] = mapped_column(String(48), nullable=False)


class AccountsTbl(Base):
    __tablename__ = 'AccountsTbl'
    __table_args__ = (
        Index('AccountId_UNIQUE', 'AccountId', unique=True),
    )

    AccountId: Mapped[int] = mapped_column(Integer, primary_key=True)
    AccountName: Mapped[str] = mapped_column(String(64), nullable=False)
    AccountTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    DateTimeCreatedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    DateTimeDeactivatedUtc: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AckMessageTbl(Base):
    __tablename__ = 'AckMessageTbl'
    __table_args__ = (
        Index('AckMessageTbl_DeviceId', 'DeviceId'),
    )

    AckMessageId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAck: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Nonce: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class BleBeaconAssTbl(Base):
    __tablename__ = 'BleBeaconAssTbl'
    __table_args__ = (
        Index('BleBeaconAssTbl_BeaconId', 'BeaconId'),
        Index('BleBeaconAssTbl_DeviceId', 'DeviceId'),
        Index('BleBeaconAssTbl_StartAss', 'StartAss'),
        Index('BleBeaconAssTbl_StopAss', 'StopAss')
    )

    BleBeaconAssTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    BeaconId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LastRssi: Mapped[int] = mapped_column(Integer, nullable=False)
    LastRssiTime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    StartAss: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    StopAss: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class BleBeaconLocTbl(Base):
    __tablename__ = 'BleBeaconLocTbl'
    __table_args__ = (
        Index('BleBeaconLocTbl_AccountId', 'AccountId'),
        Index('DeviceId', 'DeviceId', unique=True)
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    BeaconXyWeight: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False, server_default=text("'1'"))
    BeaconFloor: Mapped[int] = mapped_column(Integer, nullable=False)
    BeaconFloorWeight: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False, server_default=text("'1'"))
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class ByteBufferTransferMessageICLETbl(Base):
    __tablename__ = 'ByteBufferTransferMessageICLETbl'
    __table_args__ = (
        Index('ByteBufferTransferMessageICLETbl_DeviceId', 'DeviceId'),
        Index('ByteBufferTransferMessageICLETbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class CertificatesTbl(Base):
    __tablename__ = 'CertificatesTbl'
    __table_args__ = (
        Index('CertificatesTbl_AccountId', 'AccountId'),
    )

    CertificatesTblId: Mapped[int] = mapped_column(Integer, primary_key=True)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    CertificateName: Mapped[str] = mapped_column(String(64), nullable=False)
    FileName: Mapped[str] = mapped_column(String(64), nullable=False)
    FilePath: Mapped[str] = mapped_column(String(256), nullable=False)
    Subject: Mapped[str] = mapped_column(String(64), nullable=False)
    Issuer: Mapped[str] = mapped_column(String(64), nullable=False)
    Secret: Mapped[str] = mapped_column(String(832), nullable=False)
    ValidFrom: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    ValidTo: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class ConfigurationMessageDownlinkTankTrackTbl(Base):
    __tablename__ = 'ConfigurationMessageDownlinkTankTrackTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionMessageEnabled: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccelerometerEnabled: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    ReedSwitchEnabled: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    InMotionMeasurementPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatMeasurementPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatReportInterval: Mapped[int] = mapped_column(Integer, nullable=False)
    Alarm1Threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    Alarm2Threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    Alarm3Threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    AlarmHysteresis: Mapped[int] = mapped_column(Integer, nullable=False)
    AccThresh: Mapped[int] = mapped_column(Integer, nullable=False)
    AccDur: Mapped[int] = mapped_column(Integer, nullable=False)
    AccStopMotion: Mapped[int] = mapped_column(Integer, nullable=False)
    AdcMeasurementTime: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ConfigurationMessageTankTrackTbl(Base):
    __tablename__ = 'ConfigurationMessageTankTrackTbl'
    __table_args__ = (
        Index('ConfigurationMessageTankTrackTbl_DeviceId', 'DeviceId'),
        Index('ConfigurationMessageTankTrackTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionMessageEnabled: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccelerometerEnabled: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    ReedSwitchEnabled: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    InMotionMeasurementPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatMeasurementPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatReportInterval: Mapped[int] = mapped_column(Integer, nullable=False)
    Alarm1Threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    Alarm2Threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    Alarm3Threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    AlarmHysteresis: Mapped[int] = mapped_column(Integer, nullable=False)
    AccThresh: Mapped[int] = mapped_column(Integer, nullable=False)
    AccDur: Mapped[int] = mapped_column(Integer, nullable=False)
    AccStopMotion: Mapped[int] = mapped_column(Integer, nullable=False)
    AdcMeasurementTime: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class CoreTrackGatewayFirmwareMsgTbl(Base):
    __tablename__ = 'CoreTrackGatewayFirmwareMsgTbl'
    __table_args__ = (
        Index('CoreTrackGatewayFirmwareMsgTbl_AccountId', 'AccountId'),
        Index('CoreTrackGatewayFirmwareMsgTbl_DeviceId', 'DeviceId'),
        Index('CoreTrackGatewayFirmwareMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Bootloader9160Version: Mapped[int] = mapped_column(Integer, nullable=False)
    Application9160Version: Mapped[int] = mapped_column(Integer, nullable=False)
    Bootloader52840Version: Mapped[int] = mapped_column(Integer, nullable=False)
    Application52840Version: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class CoreTrackGatewayKeysTbl(Base):
    __tablename__ = 'CoreTrackGatewayKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class CoreTrackGatewayLastNonceTbl(Base):
    __tablename__ = 'CoreTrackGatewayLastNonceTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LastNonce: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)


class DefaultTagCheckinsTbl(Base):
    __tablename__ = 'DefaultTagCheckinsTbl'
    __table_args__ = (
        Index('DefaultTagCheckinsTb_DeviceId', 'DeviceId'),
        Index('DefaultTagCheckinsTb_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    Rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    EncryptedData: Mapped[str] = mapped_column(String(5464), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    GatewayId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DataSource: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("'1'"))
    Longitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    latitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))


class DeviceEndpointsTbl(Base):
    __tablename__ = 'DeviceEndpointsTbl'
    __table_args__ = (
        Index('DeviceEndpointId', 'DeviceEndpointId', unique=True),
        Index('IX_DeviceEndpointsTbl_DeviceId', 'DeviceId')
    )

    DeviceEndpointId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    EndpointId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Associated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    Disassociated: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class DeviceTypesTbl(Base):
    __tablename__ = 'DeviceTypesTbl'
    __table_args__ = (
        Index('DeviceTypeId', 'DeviceTypeId', unique=True),
        Index('DeviceTypeString', 'DeviceTypeString', unique=True)
    )

    DeviceTypeId: Mapped[int] = mapped_column(Integer, primary_key=True)
    DeviceTypeString: Mapped[str] = mapped_column(String(32), nullable=False)
    DeviceDataTblName: Mapped[Optional[str]] = mapped_column(String(48))
    DeviceKeysTblName: Mapped[Optional[str]] = mapped_column(String(48))
    DeviceKeysArchiveTblName: Mapped[Optional[str]] = mapped_column(String(48))


class DevicesArchiveTbl(Base):
    __tablename__ = 'DevicesArchiveTbl'
    __table_args__ = (
        Index('DevicesArchiveTbl_AccountId', 'AccountId'),
        Index('DevicesArchiveTbl_DeviceId', 'DeviceId')
    )

    DevicesArchiveTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    DevVariantId: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsAssigned: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AddedTimeUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    DateTimeArchivedUtc: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class DevicesTbl(Base):
    __tablename__ = 'DevicesTbl'
    __table_args__ = (
        Index('DeviceId_UNIQUE', 'DeviceId', unique=True),
        Index('DeviceTblId', 'DeviceTblId', unique=True),
        Index('IX_DevicesTbl_DeviceId', 'DeviceId')
    )

    DeviceTblId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsAssigned: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AddedTimeUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    DevVariantId: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    DeletedTimeUtc: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class DistFromTbl(Base):
    __tablename__ = 'DistFromTbl'

    DistFromTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ActLat: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    ActLon: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    DistOff: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    LoRaLocEstTblId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeRx: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    CalculationType: Mapped[int] = mapped_column(Integer, nullable=False)


class DownlinkMessagesTbl(Base):
    __tablename__ = 'DownlinkMessagesTbl'
    __table_args__ = (
        Index('DownlinkMessagesTbl_DeviceId', 'DeviceId'),
        Index('DownlinkMessagesTbl_DeviceTypeId', 'DeviceTypeId')
    )

    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeQueued: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    NonceSent: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAcked: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsNaked: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Message: Mapped[str] = mapped_column(String(4096), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class EndpointsTbl(Base):
    __tablename__ = 'EndpointsTbl'
    __table_args__ = (
        Index('EndpointId', 'EndpointId', unique=True),
    )

    EndpointId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    EndpointUrl: Mapped[str] = mapped_column(String(256), nullable=False)
    EncryptionType: Mapped[int] = mapped_column(Integer, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    ConsecutiveFails: Mapped[int] = mapped_column(Integer, nullable=False)
    Priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    AuthType: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    AuthUrl: Mapped[Optional[str]] = mapped_column(String(256))
    Auth: Mapped[Optional[str]] = mapped_column(String(832))
    AuthToken: Mapped[Optional[str]] = mapped_column(String(832))
    AuthTokenKey: Mapped[Optional[str]] = mapped_column(String(64))
    AuthTokenType: Mapped[Optional[str]] = mapped_column(String(64))
    AuthTokenExpiration: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    AuthTokenExpirationKey: Mapped[Optional[str]] = mapped_column(String(64))
    AuthTokenUpdated: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    AuthTokenHeader: Mapped[Optional[str]] = mapped_column(String(45))


class EnvironmentsTbl(Base):
    __tablename__ = 'EnvironmentsTbl'

    EnvironmentsTblId: Mapped[int] = mapped_column(Integer, primary_key=True)
    EnvironmentKey: Mapped[str] = mapped_column(String(64), nullable=False)
    EnvironmentValue: Mapped[str] = mapped_column(String(64), nullable=False)


class ErrorCodeTbl(Base):
    __tablename__ = 'ErrorCodeTbl'

    ErrorCode: Mapped[int] = mapped_column(Integer, primary_key=True)
    ErrorMessage: Mapped[Optional[str]] = mapped_column(String(50))


class FirmwareImagesTbl(Base):
    __tablename__ = 'FirmwareImagesTbl'

    FwVersionInfo: Mapped[int] = mapped_column(Integer, primary_key=True)
    FwCrc: Mapped[int] = mapped_column(Integer, nullable=False)
    ImageLength: Mapped[int] = mapped_column(Integer, nullable=False)
    FwType: Mapped[int] = mapped_column(Integer, nullable=False)
    FwVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    IsGoldenImage: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsProductionImage: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Filename: Mapped[str] = mapped_column(String(40), nullable=False)


class FirmwareMessageICLETbl(Base):
    __tablename__ = 'FirmwareMessageICLETbl'
    __table_args__ = (
        Index('FirmwareMessageICLETbl_DeviceId', 'DeviceId'),
        Index('FirmwareMessageICLETbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    BootloaderVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    ApplicationVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class FirmwareMessageTankTrackTbl(Base):
    __tablename__ = 'FirmwareMessageTankTrackTbl'
    __table_args__ = (
        Index('FirmwareMessageTankTrackTbl_DeviceId', 'DeviceId'),
        Index('FirmwareMessageTankTrackTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    BootloaderVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    ApplicationVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class FirmwareUpdateMessageTbl(Base):
    __tablename__ = 'FirmwareUpdateMessageTbl'
    __table_args__ = (
        Index('FirmwareUpdateMessageTbl_DeviceId', 'DeviceId'),
        Index('FirmwareUpdateMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    NumberOfPages: Mapped[int] = mapped_column(Integer, nullable=False)
    FirmwareVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    ImageChecksum: Mapped[int] = mapped_column(Integer, nullable=False)
    ImageChunkLength: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    CurrentPage: Mapped[int] = mapped_column(Integer, nullable=False)


class FirmwareUpdatePrepareMsgTbl(Base):
    __tablename__ = 'FirmwareUpdatePrepareMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    FirmwareVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    NumberOfBytes: Mapped[int] = mapped_column(Integer, nullable=False)
    ImageChecksum: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class FirmwareUpdateResetMessageTbl(Base):
    __tablename__ = 'FirmwareUpdateResetMessageTbl'
    __table_args__ = (
        Index('FirmwareUpdateResetMessageTbl_DeviceId', 'DeviceId'),
        Index('FirmwareUpdateResetMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    ResetKey: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class FirmwareUpdateResponseMessageTbl(Base):
    __tablename__ = 'FirmwareUpdateResponseMessageTbl'
    __table_args__ = (
        Index('FirmwareUpdateResponseMessageTbl_DeviceId', 'DeviceId'),
        Index('FirmwareUpdateResponseMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    FirmwareDownloadVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    NextPageRequested: Mapped[int] = mapped_column(Integer, nullable=False)
    NumberOfChunksRequested: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class FirmwareUpdateV2MsgTbl(Base):
    __tablename__ = 'FirmwareUpdateV2MsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    CurrentPage: Mapped[int] = mapped_column(Integer, nullable=False)
    NumBytesSent: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class ForwardFailTbl(Base):
    __tablename__ = 'ForwardFailTbl'

    ForwardFailTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceEndpointId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    CheckInId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    FailedTime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    NumberAttempts: Mapped[int] = mapped_column(Integer, nullable=False)
    HttpResponse: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    EndpointId: Mapped[Optional[int]] = mapped_column(BigInteger)
    TimeToForward: Mapped[Optional[int]] = mapped_column(BigInteger)
    DeviceTypeId: Mapped[Optional[int]] = mapped_column(Integer)
    MessageTypeId: Mapped[Optional[int]] = mapped_column(Integer)


class ForwardSuccessTbl(Base):
    __tablename__ = 'ForwardSuccessTbl'

    ForwardSuccessTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceEndpointId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    CheckInId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ForwardTime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    EndpointId: Mapped[Optional[int]] = mapped_column(BigInteger)
    TimeToForward: Mapped[Optional[int]] = mapped_column(BigInteger)
    DeviceTypeId: Mapped[Optional[int]] = mapped_column(Integer)
    MessageTypeId: Mapped[Optional[int]] = mapped_column(Integer)


class FreshTrackCheckinsTbl(Base):
    __tablename__ = 'FreshTrackCheckinsTbl'
    __table_args__ = (
        Index('FreshTrackCheckinsTbl_DeviceId', 'DeviceId'),
        Index('FreshTrackCheckinsTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    Rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    EncryptedData: Mapped[str] = mapped_column(String(5464), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    GatewayId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    Latitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Longitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    DataSource: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("'1'"))


class FreshTrackTemperatureOffsetTbl(Base):
    __tablename__ = 'FreshTrackTemperatureOffsetTbl'
    __table_args__ = (
        Index('FreshTrackTemperatureOffsetTbl_DeviceId', 'DeviceId'),
    )

    OffsetId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TempOffset: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))


class FuotaListsTbl(Base):
    __tablename__ = 'FuotaListsTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ReleaseList: Mapped[int] = mapped_column(Integer, nullable=False)


class FuotaReleaseListDescriptionTbl(Base):
    __tablename__ = 'FuotaReleaseListDescriptionTbl'
    __table_args__ = (
        Index('ReleaseList_UNIQUE', 'ReleaseList', unique=True),
    )

    ReleaseList: Mapped[int] = mapped_column(Integer, primary_key=True)
    Description: Mapped[str] = mapped_column(String(256), nullable=False)


class FuotaTbl(Base):
    __tablename__ = 'FuotaTbl'

    FuotaId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    FwVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    FilePath: Mapped[str] = mapped_column(String(255), nullable=False)
    ReleaseList: Mapped[int] = mapped_column(Integer, nullable=False)
    Released: Mapped[Any] = mapped_column(BIT(1), nullable=False)


class ICLEKeysTbl(Base):
    __tablename__ = 'ICLEKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class ICLELastNonceTbl(Base):
    __tablename__ = 'ICLELastNonceTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LastNonce: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)


class IclePowerTbl(Base):
    __tablename__ = 'IclePowerTbl'
    __table_args__ = (
        Index('IclePowerTbl_AccountId', 'AccountId'),
        Index('IclePowerTbl_DeviceId', 'DeviceId', 'Channel'),
        Index('IclePowerTbl_TimeStamp', 'TimeStamp')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeStamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Channel: Mapped[int] = mapped_column(Integer, nullable=False)
    Current: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Voltage: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class IssuesTbl(Base):
    __tablename__ = 'IssuesTbl'
    __table_args__ = (
        Index('IssuesTbl_DeviceId', 'DeviceId'),
        Index('IssuesTbl_DeviceTypeId', 'DeviceTypeId')
    )

    IssuesTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    ErrorCode: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrack1CMsgTbl(Base):
    __tablename__ = 'JumpTrack1CMsgTbl'
    __table_args__ = (
        Index('JumpTrack1CMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrack1CMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrack1CMsgTbl_TimeOfFix', 'TimeOfFix'),
        Index('JumpTrack1CMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AltitudeGps: Mapped[int] = mapped_column(Integer, nullable=False)
    AltitudeCalculated: Mapped[int] = mapped_column(Integer, nullable=False)
    GroundSpeed: Mapped[int] = mapped_column(Integer, nullable=False)
    Heading: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AirPressureInHg: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Temperature: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DataSource: Mapped[int] = mapped_column(Integer, nullable=False)
    Crc: Mapped[int] = mapped_column(Integer, nullable=False)
    IsGpsIndoors: Mapped[Optional[Any]] = mapped_column(BIT(1))
    BatteryVoltage: Mapped[Optional[int]] = mapped_column(Integer)
    BatteryPercentage: Mapped[Optional[int]] = mapped_column(Integer)
    AverageForce: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    MaxForce: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    NonceReceived: Mapped[Optional[int]] = mapped_column(Integer)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    FixType: Mapped[Optional[int]] = mapped_column(Integer)
    NumSatellites: Mapped[Optional[int]] = mapped_column(Integer)
    PsmState: Mapped[Optional[int]] = mapped_column(Integer)
    Pdop: Mapped[Optional[int]] = mapped_column(Integer)
    BmsTemp: Mapped[Optional[int]] = mapped_column(Integer)
    GpsVertAccuracy: Mapped[Optional[int]] = mapped_column(Integer)
    EmergencyEventId: Mapped[Optional[int]] = mapped_column(Integer)


class JumpTrackBeaconAssTbl(Base):
    __tablename__ = 'JumpTrackBeaconAssTbl'
    __table_args__ = (
        Index('JumpTrackBeaconAssTbl_BeaconId', 'BeaconId'),
        Index('JumpTrackBeaconAssTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackBeaconAssTbl_StartAss', 'StartAss'),
        Index('JumpTrackBeaconAssTbl_StopAss', 'StopAss')
    )

    BeaconAssTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    BeaconId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LastRssi: Mapped[int] = mapped_column(Integer, nullable=False)
    LastRssiTime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    StartAss: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    StopAss: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class JumpTrackBeaconCheckinTbl(Base):
    __tablename__ = 'JumpTrackBeaconCheckinTbl'
    __table_args__ = (
        Index('JumpTrackBeaconCheckinTbl_AccountId', 'AccountId'),
        Index('JumpTrackBeaconCheckinTbl_BeaconId', 'BeaconId'),
        Index('JumpTrackBeaconCheckinTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackBeaconCheckinTbl_TimeOfFix', 'TimeOfFix')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    BeaconId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AltitudeCalculated: Mapped[int] = mapped_column(Integer, nullable=False)
    GroundSpeed: Mapped[int] = mapped_column(Integer, nullable=False)
    Heading: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackBiometricMsgTbl(Base):
    __tablename__ = 'JumpTrackBiometricMsgTbl'
    __table_args__ = (
        Index('JumpTrackBiometricMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackBiometricMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackBiometricMsgTbl_TimeOfData', 'TimeOfData')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfData: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    NumHeartrateSamp: Mapped[int] = mapped_column(Integer, nullable=False)
    MaxHeartrate: Mapped[int] = mapped_column(Integer, nullable=False)
    MinHeartrate: Mapped[int] = mapped_column(Integer, nullable=False)
    AvgHeartrate: Mapped[int] = mapped_column(Integer, nullable=False)
    PulseOxPercent: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfPulseOx: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackBleBeaconConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackBleBeaconConfigMsgTbl'
    __table_args__ = (
        Index('JumpTrackBleBeaconConfigMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackBleBeaconConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackBleBeaconConfigMsgTbl_TimeOfConfig', 'TimeOfConfig')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    BeaconPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    BeaconDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    BeaconPower: Mapped[int] = mapped_column(Integer, nullable=False)
    BleSessionKeyCrc: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackBleKeysArchiveTbl(Base):
    __tablename__ = 'JumpTrackBleKeysArchiveTbl'

    Id: Mapped[int] = mapped_column(Integer, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    DateTimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class JumpTrackBleKeysTbl(Base):
    __tablename__ = 'JumpTrackBleKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackBleLabelMsgTbl(Base):
    __tablename__ = 'JumpTrackBleLabelMsgTbl'
    __table_args__ = (
        Index('JumpTrackBleLabelMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackBleLabelMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackBleLabelMsgTbl_GroupId', 'GroupId'),
        Index('JumpTrackBleLabelMsgTbl_TimeNameAssigned', 'TimeNameAssigned')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    FromDeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    GroupId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeNameAssigned: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Label: Mapped[str] = mapped_column(String(16), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackBootMessageTbl(Base):
    __tablename__ = 'JumpTrackBootMessageTbl'
    __table_args__ = (
        Index('JumpTrackBootMessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackBootMessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackBootMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    BootReason: Mapped[int] = mapped_column(Integer, nullable=False)
    NumberOfExceptions: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfBoot: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackConfigDownlinkMsgTbl(Base):
    __tablename__ = 'JumpTrackConfigDownlinkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('JumpTrackConfigDownlinkMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackConfigDownlinkMsgTbl_DownlinkMessageId', 'DownlinkMessageId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    GpsHeartbeatPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ContMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    StopMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpStateGpsPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpStateTime: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallAltThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpTriggerAltChange: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackConfigMsgTbl'
    __table_args__ = (
        Index('JumpTrackConfigMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackConfigMsgTbl_TimeOfConfig', 'TimeOfConfig'),
        Index('JumpTrackConfigMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    GpsHeartbeatPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ContMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    StopMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpStateGpsPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpStateTime: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallAltThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpTriggerAltChange: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackEmerEventRespMsgTbl(Base):
    __tablename__ = 'JumpTrackEmerEventRespMsgTbl'
    __table_args__ = (
        Index('JumpTrackEmerEventRespMsgTbl_DeviceId', 'DeviceId'),
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    EmergencyEventId: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackEmergencyConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackEmergencyConfigDnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('JumpTrackEmergencyConfigDnlnkMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackEmergencyConfigDnlnkMsgTbl_DownlinkMessageId', 'DownlinkMessageId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeLimit: Mapped[int] = mapped_column(Integer, nullable=False)
    TapThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    TapShockWindow: Mapped[int] = mapped_column(Integer, nullable=False)
    TapQuietWindow: Mapped[int] = mapped_column(Integer, nullable=False)
    TapLatencyWindow: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackEmergencyConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackEmergencyConfigMsgTbl'
    __table_args__ = (
        Index('JumpTrackEmergencyConfigMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackEmergencyConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackEmergencyConfigMsgTbl_TimeOfEmConfig', 'TimeOfEmConfig'),
        Index('JumpTrackEmergencyConfigMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfEmConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeLimit: Mapped[int] = mapped_column(Integer, nullable=False)
    TapThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    TapShockWindow: Mapped[int] = mapped_column(Integer, nullable=False)
    TapQuietWindow: Mapped[int] = mapped_column(Integer, nullable=False)
    TapLatencyWindow: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackEmergencyConfigV2DnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackEmergencyConfigV2DnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('JumpTrackEmergencyConfigDnlnkMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackEmergencyConfigDnlnkMsgTbl_DownlinkMessageId', 'DownlinkMessageId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeLimit: Mapped[int] = mapped_column(Integer, nullable=False)
    BtnActivationTime: Mapped[int] = mapped_column(Integer, nullable=False)
    BtnTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackEmergencyConfigV2MsgTbl(Base):
    __tablename__ = 'JumpTrackEmergencyConfigV2MsgTbl'
    __table_args__ = (
        Index('JumpTrackEmergencyConfigMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackEmergencyConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackEmergencyConfigMsgTbl_TimeOfEmConfig', 'TimeOfEmConfig'),
        Index('JumpTrackEmergencyConfigMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfEmConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeLimit: Mapped[int] = mapped_column(Integer, nullable=False)
    BtnActivationTime: Mapped[int] = mapped_column(Integer, nullable=False)
    BtnTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackFallConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackFallConfigDnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('JumpTrackFallConfigDnlnkMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackFallConfigDnlnkMsgTbl_DownlinkMessageId', 'DownlinkMessageId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpStateGpsReportPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpStateTime: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallAccThresh: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallAccDur: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallAltChangeThresh: Mapped[int] = mapped_column(Integer, nullable=False)
    AltChangeJumpTrig: Mapped[int] = mapped_column(Integer, nullable=False)
    NumAltStableSamples: Mapped[int] = mapped_column(Integer, nullable=False)
    AltStabilityThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackFallConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackFallConfigMsgTbl'
    __table_args__ = (
        Index('JumpTrackFallConfigMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackFallConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackFallConfigMsgTbl_TimeOfConfig', 'TimeOfConfig'),
        Index('JumpTrackFallConfigMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpModeEnabled: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    JumpStateGpsReportPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    JumpStateTime: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallAccThresh: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallAccDur: Mapped[int] = mapped_column(Integer, nullable=False)
    FreeFallAltChangeThresh: Mapped[int] = mapped_column(Integer, nullable=False)
    AltChangeJumpTrig: Mapped[int] = mapped_column(Integer, nullable=False)
    NumAltStableSamples: Mapped[int] = mapped_column(Integer, nullable=False)
    AltStabilityThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackFirmwareMessageTbl(Base):
    __tablename__ = 'JumpTrackFirmwareMessageTbl'
    __table_args__ = (
        Index('JumpTrackFirmwareMessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackFirmwareMessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackFirmwareMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    BootloaderVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    ApplicationVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackFirmwareV2MessageTbl(Base):
    __tablename__ = 'JumpTrackFirmwareV2MessageTbl'
    __table_args__ = (
        Index('JumpTrackFirmwareMessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackFirmwareMessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackFirmwareMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Bootloader9160Version: Mapped[int] = mapped_column(Integer, nullable=False)
    Application9160Version: Mapped[int] = mapped_column(Integer, nullable=False)
    Bootloader52833Version: Mapped[int] = mapped_column(Integer, nullable=False)
    Application52833Version: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackFreeFallMessageTbl(Base):
    __tablename__ = 'JumpTrackFreeFallMessageTbl'
    __table_args__ = (
        Index('JumpTrackFreeFallMessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackFreeFallMessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackFreeFallMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    FallTime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[Optional[int]] = mapped_column(Integer)
    IsJumpModeEnabled: Mapped[Optional[Any]] = mapped_column(BIT(1))


class JumpTrackGndConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackGndConfigDnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('JumpTrackEmergencyConfigDnlnkMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackEmergencyConfigDnlnkMsgTbl_DownlinkMessageId', 'DownlinkMessageId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    GpsHeartbeatPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ContMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    StopMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowStart: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowEnd: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackGndConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackGndConfigMsgTbl'
    __table_args__ = (
        Index('JumpTrackGndConfigMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackGndConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackGndConfigMsgTbl_TimeOfConfig', 'TimeOfConfig'),
        Index('JumpTrackGndConfigMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    GpsHeartbeatPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ContMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    StopMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowStart: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowEnd: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackGndConfigV2DnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackGndConfigV2DnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('JumpTrackGndConfigV2DnlnkMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackGndConfigV2DnlnkMsgTbl_DownlinkMessageId', 'DownlinkMessageId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    GpsHeartbeatPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ContMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionStopTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowStart: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowEnd: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionAcqOnTime: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionInitAcqOnTime: Mapped[int] = mapped_column(Integer, nullable=False)
    Reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackGndConfigV2MsgTbl(Base):
    __tablename__ = 'JumpTrackGndConfigV2MsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    GpsHeartbeatPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ContMotionPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionStopTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartbeatAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionAcqTimeout: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowStart: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowEnd: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionAcqOnTime: Mapped[int] = mapped_column(Integer, nullable=False)
    MotionInitAcqOnTime: Mapped[int] = mapped_column(Integer, nullable=False)
    Reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackGpsConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackGpsConfigDnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    TargetFixAccuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    TargetFixPdop: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackGpsConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackGpsConfigMsgTbl'
    __table_args__ = (
        Index('JumpTrackLoRaConfigMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackLoRaConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackLoRaConfigMsgTbl_TimeOfGpsConfig', 'TimeOfGpsConfig'),
        Index('JumpTrackLoRaConfigMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfGpsConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    TargetFixAccuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    TargetFixPdop: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackGroupDevicesTbl(Base):
    __tablename__ = 'JumpTrackGroupDevicesTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('JumpTrackGroupDevicesTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackGroupDevicesTbl_GroupId', 'GroupId')
    )

    JumpTrackGroupDevicesTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    GroupId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AddedToGroup: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    AcceptedGroup: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class JumpTrackGroupJoinTbl(Base):
    __tablename__ = 'JumpTrackGroupJoinTbl'
    __table_args__ = (
        Index('JumpTrackGroupJoinTbl_GroupId', 'GroupId'),
        Index('JumpTrackGroupJoinTbl_RequestCreated', 'RequestCreatedAt')
    )

    JoinRequestId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    GroupId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    RequestId: Mapped[str] = mapped_column(CHAR(88), nullable=False)
    RequestCreatedAt: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)


class JumpTrackGroupKeysTbl(Base):
    __tablename__ = 'JumpTrackGroupKeysTbl'

    GroupId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MacSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MacKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MacKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackGroupPlaneTbl(Base):
    __tablename__ = 'JumpTrackGroupPlaneTbl'
    __table_args__ = (
        Index('JumpTrackGroupPlaneTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackGroupPlaneTbl_GroupId', 'GroupId')
    )

    JumpTrackGroupPlaneTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    GroupId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AddedToGroup: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    AcceptedGroup: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    RemovedFromGroup: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class JumpTrackGroupPositionCheckinsTbl(Base):
    __tablename__ = 'JumpTrackGroupPositionCheckinsTbl'
    __table_args__ = (
        Index('JumpTrackGroupPositionCheckinsTbl_AccountId', 'AccountId'),
        Index('JumpTrackGroupPositionCheckinsTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackGroupPositionCheckinsTbl_GroupId', 'GroupId'),
        Index('JumpTrackGroupPositionCheckinsTbl_TimeOfFix', 'TimeOfFix')
    )

    JumpTrackGroupPositionCheckinsTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    FromDeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    GroupId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    GpsAccuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackHardwareFailureMessageTbl(Base):
    __tablename__ = 'JumpTrackHardwareFailureMessageTbl'
    __table_args__ = (
        Index('JumpTrackPositionMessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackPositionMessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackPositionMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    AccFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAccComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AltFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAltComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsAltIntFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    GpsFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsGpsComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Sx1262Failures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsSx1262ComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsSx1262PllFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IpcFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsIpcComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackHardwareFailureV2MsgTbl(Base):
    __tablename__ = 'JumpTrackHardwareFailureV2MsgTbl'
    __table_args__ = (
        Index('JumpTrackHardwareFailureV2MsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackHardwareFailureV2MsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackHardwareFailureV2MsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    FailureTime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAccComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AltFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAltComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsAltIntFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    GpsFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsGpsComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsCrystalFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Sx1262Failures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsSx1262ComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsSx1262PllFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IpcFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsIpcComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    BmsFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsBmsComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    ExtFlashFailure: Mapped[int] = mapped_column(Integer, nullable=False)
    IsExtFlashComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SecElementFailure: Mapped[int] = mapped_column(Integer, nullable=False)
    IsSecElementComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackHipsConfigArchiveTbl(Base):
    __tablename__ = 'JumpTrackHipsConfigArchiveTbl'

    RecordId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    GroupId: Mapped[int] = mapped_column(Integer, nullable=False)
    SourceUserId: Mapped[int] = mapped_column(Integer, nullable=False)
    TimePairedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeUnpairedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class JumpTrackHipsConfigDnlnkTbl(Base):
    __tablename__ = 'JumpTrackHipsConfigDnlnkTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    GroupId: Mapped[int] = mapped_column(Integer, nullable=False)
    SourceUserId: Mapped[int] = mapped_column(Integer, nullable=False)
    TimePairedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackHipsConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackHipsConfigMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    ReportPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ForceCheckin: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    ScanConstantly: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Mode: Mapped[int] = mapped_column(Integer, nullable=False)
    GroupCode: Mapped[int] = mapped_column(Integer, nullable=False)
    SourceUserId: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackHipsSensorDataMsgTbl(Base):
    __tablename__ = 'JumpTrackHipsSensorDataMsgTbl'
    __table_args__ = (
        Index('JumpTrackHipsSensorDataMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackHipsSensorDataMsgTbl_DeviceId_TimeOfMeasurement', 'DeviceId', 'TimeOfMeasurement')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfMeasurement: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    GroupCode: Mapped[int] = mapped_column(Integer, nullable=False)
    SourceUserId: Mapped[int] = mapped_column(Integer, nullable=False)
    HsiDataValue: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    HrDataValue: Mapped[int] = mapped_column(Integer, nullable=False)
    EstimatedCoreTemp: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    SkinTemp: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    NII: Mapped[int] = mapped_column(Integer, nullable=False)
    Risk: Mapped[int] = mapped_column(Integer, nullable=False)
    Confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    HipsBatteryLife: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackIridiumConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackIridiumConfigDnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IridiumCooldown: Mapped[int] = mapped_column(Integer, nullable=False)
    WaitSbdixResponseTries: Mapped[int] = mapped_column(Integer, nullable=False)
    SbdixErrorAttempts: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackIridiumConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackIridiumConfigMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    ShouldSendWithCell: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IridiumCooldown: Mapped[int] = mapped_column(Integer, nullable=False)
    WaitSbdixResponseTries: Mapped[int] = mapped_column(Integer, nullable=False)
    SbdixErrorAttempts: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackIridiumStatusMsgTbl(Base):
    __tablename__ = 'JumpTrackIridiumStatusMsgTbl'
    __table_args__ = (
        Index('JumpTrackIridiumStatusMsgTbl_DeviceId', 'DeviceId'),
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfAttempt: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeSpentSending: Mapped[int] = mapped_column(Integer, nullable=False)
    MsgSendSuccess: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SignalQuality: Mapped[int] = mapped_column(Integer, nullable=False)
    SendAttempts: Mapped[int] = mapped_column(Integer, nullable=False)
    NumBytesSent: Mapped[int] = mapped_column(Integer, nullable=False)
    NumBytesReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    SbdixStatus: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackKeysArchiveTbl(Base):
    __tablename__ = 'JumpTrackKeysArchiveTbl'

    Id: Mapped[int] = mapped_column(Integer, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    DateTimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class JumpTrackKeysTbl(Base):
    __tablename__ = 'JumpTrackKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackLastNonceTbl(Base):
    __tablename__ = 'JumpTrackLastNonceTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LastNonce: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackLoRaBeacon99MessageTbl(Base):
    __tablename__ = 'JumpTrackLoRaBeacon99MessageTbl'
    __table_args__ = (
        Index('JumpTrackLoRaBeacon99MessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackLoRaBeacon99MessageTbl_BeaconDeviceId', 'BeaconDeviceId'),
        Index('JumpTrackLoRaBeacon99MessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackLoRaBeacon99MessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    GroundSpeed: Mapped[int] = mapped_column(Integer, nullable=False)
    Heading: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AirPressureInHg: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AltitudeCalculated: Mapped[int] = mapped_column(Integer, nullable=False)
    BeaconDeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    Rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    WasReplaced: Mapped[Optional[Any]] = mapped_column(BIT(1))


class JumpTrackLoRaConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackLoRaConfigDnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    SessionConfigCrc: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackLoRaConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackLoRaConfigMsgTbl'
    __table_args__ = (
        Index('JumpTrackLoRaConfigMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackLoRaConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackLoRaConfigMsgTbl_TimeOfLoRaConfigg', 'TimeOfLoRaConfig'),
        Index('JumpTrackLoRaConfigMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfLoRaConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    SessionConfigCrc: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackLoRaHardwareFailureMessageTbl(Base):
    __tablename__ = 'JumpTrackLoRaHardwareFailureMessageTbl'
    __table_args__ = (
        Index('JumpTrackLoRaHardwareFailureMessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackLoRaHardwareFailureMessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackLoRaHardwareFailureMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAccComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AltFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAltComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsAltIntFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    GpsFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsGpsComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Sx1262Failures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsSx1262ComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsSx1262PllFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IpcFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    IsIpcComFailure: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class JumpTrackLoRaKeysArchiveTbl(Base):
    __tablename__ = 'JumpTrackLoRaKeysArchiveTbl'

    Id: Mapped[int] = mapped_column(Integer, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AppEui: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AppSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKey: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    NetSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKey: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    DateTimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class JumpTrackLoRaKeysTbl(Base):
    __tablename__ = 'JumpTrackLoRaKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    AppEui: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AppSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKey: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    NetSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKey: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackLoRaPosition97MessageTbl(Base):
    __tablename__ = 'JumpTrackLoRaPosition97MessageTbl'
    __table_args__ = (
        Index('JumpTrackLoRaPosition97MessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackLoRaPosition97MessageTbl_TimeReceived', 'TimeReceived'),
        Index('NumpTrackLoRaPosition97MessageTbl_DeviceId', 'DeviceId')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    GroundSpeed: Mapped[int] = mapped_column(Integer, nullable=False)
    Heading: Mapped[int] = mapped_column(Integer, nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AirPressureInHg: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AltitudeCalculated: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    WasReplaced: Mapped[Optional[Any]] = mapped_column(BIT(1))


class JumpTrackLoRaPositionMessageTbl(Base):
    __tablename__ = 'JumpTrackLoRaPositionMessageTbl'
    __table_args__ = (
        Index('NurJumpTrack95MessageTbl_AccountId', 'AccountId'),
        Index('NurJumpTrack95MessageTbl_DeviceId', 'DeviceId'),
        Index('NurJumpTrack95MessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AirPressureInHg: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AltitudeCalculated: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class JumpTrackModemConfigDnlnkMsgTbl(Base):
    __tablename__ = 'JumpTrackModemConfigDnlnkMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('JumpTrackModemConfigDnlnkMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackModemConfigDnlnkMsgTbl_DownlinkMessageId', 'DownlinkMessageId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ShortBackoff: Mapped[int] = mapped_column(Integer, nullable=False)
    NormalBackoff: Mapped[int] = mapped_column(Integer, nullable=False)
    LongBackoff: Mapped[int] = mapped_column(Integer, nullable=False)
    RegistrationTimeoutPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    SocketConnectionTimeoutPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ConnectionFailureThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    SocketTimeoutPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackModemConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackModemConfigMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    ShortBackoff: Mapped[int] = mapped_column(Integer, nullable=False)
    NormalBackoff: Mapped[int] = mapped_column(Integer, nullable=False)
    LongBackoff: Mapped[int] = mapped_column(Integer, nullable=False)
    RegistrationTimeoutPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    SocketConnectionTimeoutPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    ConnectionFailureThreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    SocketTimeoutPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackPoiEndpointMapTbl(Base):
    __tablename__ = 'JumpTrackPoiEndpointMapTbl'
    __table_args__ = (
        Index('JumpTrackPoiEndpointMapTbl_DeviceId', 'DeviceId'),
    )

    RecordId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    EndpointId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackPositionMessageTbl(Base):
    __tablename__ = 'JumpTrackPositionMessageTbl'
    __table_args__ = (
        Index('JumpTrackPositionMessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackPositionMessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackPositionMessageTbl_TimeOfFix', 'TimeOfFix'),
        Index('JumpTrackPositionMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AltitudeGps: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    BatteryVoltage: Mapped[Optional[int]] = mapped_column(Integer)


class JumpTrackPositionV2MessageTbl(Base):
    __tablename__ = 'JumpTrackPositionV2MessageTbl'
    __table_args__ = (
        Index('JumpTrackPositionV2MessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackPositionV2MessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackPositionV2MessageTbl_TimeOfFix', 'TimeOfFix'),
        Index('JumpTrackPositionV2MessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AltitudeGps: Mapped[int] = mapped_column(Integer, nullable=False)
    GroundSpeed: Mapped[int] = mapped_column(Integer, nullable=False)
    Heading: Mapped[int] = mapped_column(Integer, nullable=False)
    BatteryVoltage: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    WasReplaced: Mapped[Optional[Any]] = mapped_column(BIT(1))


class JumpTrackRebootMsgTbl(Base):
    __tablename__ = 'JumpTrackRebootMsgTbl'
    __table_args__ = (
        Index('JumpTrackRebootMsgTbl_AccountId', 'AccountId'),
        Index('JumpTrackRebootMsgTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackRebootMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    RebootPattern: Mapped[int] = mapped_column(Integer, nullable=False)
    RebootFlags: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackSensorMessageTbl(Base):
    __tablename__ = 'JumpTrackSensorMessageTbl'
    __table_args__ = (
        Index('JumpTrackSensorMessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackSensorMessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackSensorMessageTbl_TimeOfMeasurement', 'TimeOfMeasurement'),
        Index('JumpTrackSensorMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    AirPressureInHg: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Temperature: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AltitudeCalculated: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfMeasurement: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackSensorV2MessageTbl(Base):
    __tablename__ = 'JumpTrackSensorV2MessageTbl'
    __table_args__ = (
        Index('JumpTrackSensorV2MessageTbl_AccountId', 'AccountId'),
        Index('JumpTrackSensorV2MessageTbl_DeviceId', 'DeviceId'),
        Index('JumpTrackSensorV2MessageTbl_TimeOfMeasurement', 'TimeOfMeasurement'),
        Index('JumpTrackSensorV2MessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    AirPressureInHg: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Temperature: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AverageForce: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    MaxForce: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AltitudeCalculated: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfMeasurement: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class JumpTrackServerConfigDnlnkTbl(Base):
    __tablename__ = 'JumpTrackServerConfigDnlnkTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    Port: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ServerUrl: Mapped[Optional[str]] = mapped_column(String(132))


class JumpTrackServerConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackServerConfigMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    Port: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    ServerUrl: Mapped[Optional[str]] = mapped_column(String(132))


class JumpTrackSimConfigDnlnkTbl(Base):
    __tablename__ = 'JumpTrackSimConfigDnlnkTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMessageId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class JumpTrackSimConfigMsgTbl(Base):
    __tablename__ = 'JumpTrackSimConfigMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConfig: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    DefaultSimSelect: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class KudelskiDecryptionResultTbl(Base):
    __tablename__ = 'KudelskiDecryptionResultTbl'

    KudelskiDecryptionResultTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    RotPublicUid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    HttpResponse: Mapped[int] = mapped_column(Integer, nullable=False)
    CheckInId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    MessageTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    LastEventTime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    DecryptionSuccess: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    NumberAttempts: Mapped[Optional[int]] = mapped_column(Integer)
    TimeToDecrypt: Mapped[Optional[int]] = mapped_column(BigInteger)
    ErrorMessage: Mapped[Optional[str]] = mapped_column(String(256))


class LastLocationTbl(Base):
    __tablename__ = 'LastLocationTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('LastLocationTbl_AccountId', 'AccountId'),
        Index('LastLocationTbl_LastCheckin', 'LastCheckin'),
        Index('LastLocationTbl_LocationId', 'LocationId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LocationId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    WasManualAssignment: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    LastCheckin: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    BatteryVoltage: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    LastPosition: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    PositionLocationId: Mapped[Optional[int]] = mapped_column(Integer)
    LastFw: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    BlVersion: Mapped[Optional[int]] = mapped_column(Integer)
    FwVersion: Mapped[Optional[int]] = mapped_column(Integer)
    FwLocationId: Mapped[Optional[int]] = mapped_column(Integer)


class LoRaDownlinkEnableListTbl(Base):
    __tablename__ = 'LoRaDownlinkEnableListTbl'
    __table_args__ = (
        Index('DownlinkEnableListTbl_AccountId', 'AccountId'),
        Index('DownlinkEnableListTbl_DeviceId', 'DeviceId')
    )

    LoRaDownlinkEnableListTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LoRaDownlinkEnableList: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class LoRaDownlinkLocationMapTbl(Base):
    __tablename__ = 'LoRaDownlinkLocationMapTbl'
    __table_args__ = (
        Index('LoRaDownlinkLocationMapTbl_AccountId', 'AccountId'),
        Index('LoRaDownlinkLocationMapTbl_LoRaDownlinkTblId', 'LoRaDownlinkTblId'),
        Index('LoRaDownlinkLocationMapTbl_LocationId', 'LocationId')
    )

    LoRaDownlinkLocationMapTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaDownlinkTblId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LocationId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class LoRaDownlinkTbl(Base):
    __tablename__ = 'LoRaDownlinkTbl'
    __table_args__ = (
        Index('LoRaDownlinkTbl_AccountId', 'AccountId'),
        Index('LoRaDownlinkTbl_DeviceTypeId', 'DeviceTypeId'),
        Index('LoRaDownlinkTbl_LoRaDownlinkEnableList', 'LoRaDownlinkEnableList'),
        Index('LoRaDownlinkTbl_Port', 'Port')
    )

    LoRaDownlinkTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Port: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    MessageCompare: Mapped[str] = mapped_column(String(345), nullable=False)
    SendIfMatch: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SendConfirmed: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsAllDevices: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    MessageCompareMask: Mapped[Optional[str]] = mapped_column(String(345))
    SendPort: Mapped[Optional[int]] = mapped_column(Integer)
    SendMessage: Mapped[Optional[str]] = mapped_column(String(345))
    LoRaDownlinkEnableList: Mapped[Optional[int]] = mapped_column(BigInteger)
    NandMaskB64: Mapped[Optional[str]] = mapped_column(String(345))


class LoRaDownlinksArchiveTbl(Base):
    __tablename__ = 'LoRaDownlinksArchiveTbl'

    ArchiveId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Description: Mapped[str] = mapped_column(String(64), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    UplinkPort: Mapped[int] = mapped_column(Integer, nullable=False)
    UplinkMsgB64: Mapped[str] = mapped_column(String(345), nullable=False)
    DownlinkPort: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMsgB64: Mapped[str] = mapped_column(String(345), nullable=False)
    SendConfirmed: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SendToAll: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SendToLocations: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SendToDevices: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    TimeConfiguredUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AndMaskB64: Mapped[Optional[str]] = mapped_column(String(345))
    NandMaskB64: Mapped[Optional[str]] = mapped_column(String(345))
    MulticastGroupId: Mapped[Optional[int]] = mapped_column(BigInteger)


class LoRaDownlinksDeviceMapArchiveTbl(Base):
    __tablename__ = 'LoRaDownlinksDeviceMapArchiveTbl'

    Id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaDownlinksTblId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class LoRaDownlinksDeviceMapTbl(Base):
    __tablename__ = 'LoRaDownlinksDeviceMapTbl'
    __table_args__ = (
        Index('LoRaDownlinksDeviceMapTbl_LoRaDownlinksTblId', 'LoRaDownlinksTblId'),
    )

    Id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaDownlinksTblId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class LoRaDownlinksLocationMapArchiveTbl(Base):
    __tablename__ = 'LoRaDownlinksLocationMapArchiveTbl'

    Id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaDownlinksTblId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LocationId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class LoRaDownlinksLocationMapTbl(Base):
    __tablename__ = 'LoRaDownlinksLocationMapTbl'
    __table_args__ = (
        Index('LoRaDownlinksLocationMapTbl_LoRaDownlinksTblId', 'LoRaDownlinksTblId'),
    )

    Id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaDownlinksTblId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LocationId: Mapped[int] = mapped_column(BigInteger, nullable=False)


class LoRaDownlinksTbl(Base):
    __tablename__ = 'LoRaDownlinksTbl'
    __table_args__ = (
        Index('LoRaDownlinksTbl_AccountId', 'AccountId'),
        Index('LoRaDownlinksTbl_DeviceTypeId', 'DeviceTypeId'),
        Index('LoRaDownlinksTbl_MulticastGroupId', 'MulticastGroupId'),
        Index('LoRaDownlinksTbl_UplinkPort', 'UplinkPort')
    )

    LoRaDownlinksTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    Description: Mapped[str] = mapped_column(String(64), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    UplinkPort: Mapped[int] = mapped_column(Integer, nullable=False)
    UplinkMsgB64: Mapped[str] = mapped_column(String(345), nullable=False)
    DownlinkPort: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkMsgB64: Mapped[str] = mapped_column(String(345), nullable=False)
    SendConfirmed: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SendToAll: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SendToLocations: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SendToDevices: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    TimeConfiguredUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AndMaskB64: Mapped[Optional[str]] = mapped_column(String(345))
    NandMaskB64: Mapped[Optional[str]] = mapped_column(String(345))
    MulticastGroupId: Mapped[Optional[int]] = mapped_column(BigInteger)


class LoRaFailMessageTbl(Base):
    __tablename__ = 'LoRaFailMessageTbl'
    __table_args__ = (
        Index('LoRaFailMessageTbl_DeviceId', 'DeviceId'),
        Index('LoRaFailMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    FailureReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Port: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    Message: Mapped[Optional[str]] = mapped_column(String(345))
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class LoRaGatewayLocationMapTbl(Base):
    __tablename__ = 'LoRaGatewayLocationMapTbl'
    __table_args__ = (
        Index('LocLoRaGatewayLocationMapTbl_AccountId', 'AccountId'),
        Index('LocLoRaGatewayLocationMapTbl_LoRaGatewayId', 'LoRaGatewayId'),
        Index('LocLoRaGatewayLocationMapTbl_LocationId', 'LocationId')
    )

    LoRaGatewayLocationMapTbl: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LocationId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LoRaGatewayId: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class LoRaLocEstTbl(Base):
    __tablename__ = 'LoRaLocEstTbl'
    __table_args__ = (
        Index('LoRaLocEstTbl_AccountId', 'AccountId'),
        Index('LoRaLocEstTbl_DeviceId', 'DeviceId'),
        Index('LoRaLocEstTbl_HDop', 'HDop'),
        Index('LoRaLocEstTbl_TimeRx', 'TimeRx')
    )

    LoRaLocEstTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeRx: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Lat: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Lon: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Alt: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    HDop: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    GDop: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    NumUlPacketsUsed: Mapped[int] = mapped_column(Integer, nullable=False)
    NumGatewaysUsed: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class LoRaMulticastGatewayMapArchiveTbl(Base):
    __tablename__ = 'LoRaMulticastGatewayMapArchiveTbl'
    __table_args__ = (
        Index('LoRaMulticastGatewayMapArchiveTbl_MulticastGroupDeviceId', 'MulticastGroupDeviceId'),
    )

    ArchiveId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    MulticastGroupDeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LoRaGatewayId: Mapped[int] = mapped_column(Integer, nullable=False)
    TimePairedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaMulticastGatewayMapTbl(Base):
    __tablename__ = 'LoRaMulticastGatewayMapTbl'
    __table_args__ = (
        Index('LoRaMulticastGatewayMapTbl_LoRaGatewayId', 'LoRaGatewayId'),
        Index('LoRaMulticastGatewayMapTbl_MulticastGroupDeviceId', 'MulticastGroupDeviceId')
    )

    MapId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    MulticastGroupDeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LoRaGatewayId: Mapped[int] = mapped_column(Integer, nullable=False)
    TimePairedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaMulticastGroupsArchiveTbl(Base):
    __tablename__ = 'LoRaMulticastGroupsArchiveTbl'
    __table_args__ = (
        Index('LoRaMulticastGroupsArchiveTbl_DeviceId', 'DeviceId'),
        Index('LoRaMulticastGroupsArchiveTbl_TimeArchivedUtc', 'TimeArchivedUtc')
    )

    ArchiveTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceAddress: Mapped[int] = mapped_column(Integer, nullable=False)
    GroupName: Mapped[str] = mapped_column(String(48), nullable=False)
    GroupType: Mapped[str] = mapped_column(String(1), nullable=False)
    FCount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DataRate: Mapped[int] = mapped_column(BigInteger, nullable=False)
    Frequency: Mapped[int] = mapped_column(BigInteger, nullable=False)
    PingSlotPeriod: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeAddedToNetworkUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaMulticastGroupsTbl(Base):
    __tablename__ = 'LoRaMulticastGroupsTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceAddress: Mapped[int] = mapped_column(Integer, nullable=False)
    GroupName: Mapped[str] = mapped_column(String(48), nullable=False)
    GroupType: Mapped[str] = mapped_column(String(1), nullable=False)
    FCount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DataRate: Mapped[int] = mapped_column(BigInteger, nullable=False)
    Frequency: Mapped[int] = mapped_column(BigInteger, nullable=False)
    PingSlotPeriod: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeAddedToNetworkUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaMulticastKeysArchiveTbl(Base):
    __tablename__ = 'LoRaMulticastKeysArchiveTbl'
    __table_args__ = (
        Index('LoRaMulticastKeysArchiveTbl_TimeArchivedUtc', 'TimeArchivedUtc'),
    )

    KeysArchiveTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AppSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    AppHash: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    NetSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    NetHash: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaMulticastKeysTbl(Base):
    __tablename__ = 'LoRaMulticastKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    AppSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    AppHash: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    NetSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    NetHash: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class LoRaMulticastTypeTbl(Base):
    __tablename__ = 'LoRaMulticastTypeTbl'

    LoRaMulticastTypeId: Mapped[int] = mapped_column(Integer, primary_key=True)
    LoRaMulticastTypeName: Mapped[str] = mapped_column(String(64), nullable=False)


class LoRaMulticastsArchiveTbl(Base):
    __tablename__ = 'LoRaMulticastsArchiveTbl'

    LoRaMulticastArchiveTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    MulticastGroupDeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LoRaMulticastTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    Description: Mapped[str] = mapped_column(String(64), nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkPort: Mapped[int] = mapped_column(Integer, nullable=False)
    TxPeriodSec: Mapped[int] = mapped_column(Integer, nullable=False)
    TxOffsetSec: Mapped[int] = mapped_column(Integer, nullable=False)
    RxWindowSec: Mapped[int] = mapped_column(Integer, nullable=False)
    ScanPeriodMin: Mapped[int] = mapped_column(Integer, nullable=False)
    CallbackUtilityName: Mapped[str] = mapped_column(String(64), nullable=False)
    CallbackUrlPath: Mapped[str] = mapped_column(String(64), nullable=False)
    TimeConfiguredUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    StringCol1: Mapped[Optional[str]] = mapped_column(String(64))
    StringCol2: Mapped[Optional[str]] = mapped_column(String(64))
    StringCol3: Mapped[Optional[str]] = mapped_column(String(64))
    IntCol1: Mapped[Optional[int]] = mapped_column(Integer)
    IntCol2: Mapped[Optional[int]] = mapped_column(Integer)
    IntCol3: Mapped[Optional[int]] = mapped_column(Integer)
    DoubleCol1: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    DoubleCol2: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    DoubleCol3: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))


class LoRaMulticastsTbl(Base):
    __tablename__ = 'LoRaMulticastsTbl'
    __table_args__ = (
        Index('LoRaMulticastsTbl_DeviceTypeId', 'DeviceTypeId'),
    )

    MulticastGroupDeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaMulticastTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    Description: Mapped[str] = mapped_column(String(64), nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    DownlinkPort: Mapped[int] = mapped_column(Integer, nullable=False)
    TxPeriodSec: Mapped[int] = mapped_column(Integer, nullable=False)
    TxOffsetSec: Mapped[int] = mapped_column(Integer, nullable=False)
    RxWindowSec: Mapped[int] = mapped_column(Integer, nullable=False)
    ScanPeriodMin: Mapped[int] = mapped_column(Integer, nullable=False)
    CallbackUtilityName: Mapped[str] = mapped_column(String(64), nullable=False)
    CallbackUrlPath: Mapped[str] = mapped_column(String(64), nullable=False)
    TimeConfiguredUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    StringCol1: Mapped[Optional[str]] = mapped_column(String(64))
    StringCol2: Mapped[Optional[str]] = mapped_column(String(64))
    StringCol3: Mapped[Optional[str]] = mapped_column(String(64))
    IntCol1: Mapped[Optional[int]] = mapped_column(Integer)
    IntCol2: Mapped[Optional[int]] = mapped_column(Integer)
    IntCol3: Mapped[Optional[int]] = mapped_column(Integer)
    DoubleCol1: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    DoubleCol2: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    DoubleCol3: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))


class LoRaNetAccountMapArchiveTbl(Base):
    __tablename__ = 'LoRaNetAccountMapArchiveTbl'

    ArchiveId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    UserAccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeAssociatedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaNetAccountMapTbl(Base):
    __tablename__ = 'LoRaNetAccountMapTbl'
    __table_args__ = (
        Index('LoRaNetAccountMapTbl_UserAccountId', 'UserAccountId'),
    )

    LoRaNetAccountMapTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    UserAccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeAssociatedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaNetDevMapArchiveTbl(Base):
    __tablename__ = 'LoRaNetDevMapArchiveTbl'
    __table_args__ = (
        Index('LoRaNetDevMapArchiveTbl_DeviceId', 'DeviceId'),
        Index('LoRaNetDevMapArchiveTbl_TimeArchivedUtc', 'TimeArchivedUtc')
    )

    LoRaNetDevMapArchiveTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeAddedToNetworkUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    TimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaNetDevMapTbl(Base):
    __tablename__ = 'LoRaNetDevMapTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('LoRaNetDevMapTbl_LoRaNetworkId', 'LoRaNetworkId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeAddedToNetworkUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class LoRaNetworkGatewayTbl(Base):
    __tablename__ = 'LoRaNetworkGatewayTbl'

    LoRaGatewayId: Mapped[int] = mapped_column(Integer, primary_key=True)
    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    NetworkTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    IdentifierToNetwork: Mapped[str] = mapped_column(String(16), nullable=False)
    GatewayName: Mapped[str] = mapped_column(String(32), nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Altitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    GatewayCheckinId: Mapped[str] = mapped_column(String(32), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    GatewayNodeId: Mapped[Optional[str]] = mapped_column(String(45))


class LoRaNetworkTbl(Base):
    __tablename__ = 'LoRaNetworkTbl'

    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    NetworkTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    Description: Mapped[str] = mapped_column(String(64), nullable=False)
    TimeCreatedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    OwnerAccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    EndpointId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    TimeDeactivatedUtc: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class LoRaNetworkTypeTbl(Base):
    __tablename__ = 'LoRaNetworkTypeTbl'

    NetworkTypeId: Mapped[int] = mapped_column(Integer, primary_key=True)
    NetworkTypeName: Mapped[Optional[str]] = mapped_column(String(48))


class LoRaSentMsgTbl(Base):
    __tablename__ = 'LoRaSentMsgTbl'
    __table_args__ = (
        Index('LoRaSentMessageTbl_DeviceId', 'DeviceId'),
        Index('LoRaSentMessageTbl_DeviceTypeId', 'DeviceTypeId'),
        Index('LoRaSentMessageTbl_Port', 'Port'),
        Index('LoRaSentMessageTbl_TimeSent', 'TimeSent')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeSent: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Port: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    SentMessage: Mapped[Optional[str]] = mapped_column(String(345))
    LoRaNetworkId: Mapped[Optional[int]] = mapped_column(BigInteger)


class LoRaToaDataArchiveTbl(Base):
    __tablename__ = 'LoRaToaDataArchiveTbl'
    __table_args__ = (
        Index('LoRaToaDataTbl_AccountId', 'AccountId'),
        Index('LoRaToaDataTbl_DeviceId', 'DeviceId'),
        Index('LoRaToaDataTbl_GwId', 'GwId'),
        Index('LoRaToaDataTbl_TimeRx', 'TimeRx')
    )

    LoRaToaDataTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeRx: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    DevAddr: Mapped[int] = mapped_column(Integer, nullable=False)
    FrameCnt: Mapped[int] = mapped_column(Integer, nullable=False)
    FreqHz: Mapped[int] = mapped_column(Integer, nullable=False)
    BwHz: Mapped[int] = mapped_column(Integer, nullable=False)
    Sf: Mapped[int] = mapped_column(Integer, nullable=False)
    Rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    Snr: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    ToaSec: Mapped[int] = mapped_column(Integer, nullable=False)
    ToaNsec: Mapped[int] = mapped_column(Integer, nullable=False)
    FoHz: Mapped[int] = mapped_column(Integer, nullable=False)
    ToaUNsec: Mapped[int] = mapped_column(Integer, nullable=False)
    FoUHz: Mapped[int] = mapped_column(Integer, nullable=False)
    GwId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AntInd: Mapped[int] = mapped_column(Integer, nullable=False)
    AntLat: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AntLon: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AntAlt: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class LoRaToaDataTbl(Base):
    __tablename__ = 'LoRaToaDataTbl'
    __table_args__ = (
        Index('LoRaToaDataTbl_AccountId', 'AccountId'),
        Index('LoRaToaDataTbl_DeviceId', 'DeviceId'),
        Index('LoRaToaDataTbl_GwId', 'GwId'),
        Index('LoRaToaDataTbl_TimeRx', 'TimeRx')
    )

    LoRaToaDataTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeRx: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    DevAddr: Mapped[int] = mapped_column(Integer, nullable=False)
    FrameCnt: Mapped[int] = mapped_column(Integer, nullable=False)
    FreqHz: Mapped[int] = mapped_column(Integer, nullable=False)
    BwHz: Mapped[int] = mapped_column(Integer, nullable=False)
    Sf: Mapped[int] = mapped_column(Integer, nullable=False)
    Rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    Snr: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    ToaSec: Mapped[int] = mapped_column(Integer, nullable=False)
    ToaNsec: Mapped[int] = mapped_column(Integer, nullable=False)
    FoHz: Mapped[int] = mapped_column(Integer, nullable=False)
    ToaUNsec: Mapped[int] = mapped_column(Integer, nullable=False)
    FoUHz: Mapped[int] = mapped_column(Integer, nullable=False)
    GwId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AntInd: Mapped[int] = mapped_column(Integer, nullable=False)
    AntLat: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AntLon: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AntAlt: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class LocationReportDataTbl(Base):
    __tablename__ = 'LocationReportDataTbl'
    __table_args__ = (
        Index('LocationReportDataTbl_DeviceTypeId', 'DeviceTypeId'),
        Index('LocationReportDataTbl_LocationReportId', 'LocationReportId')
    )

    LocationReportDataTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LocationReportId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    ParamName: Mapped[str] = mapped_column(String(32), nullable=False)
    ShouldDisplay: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    ParamValue: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Count: Mapped[Optional[int]] = mapped_column(Integer)
    RangeMin: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    RangeMax: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))


class LocationReportTbl(Base):
    __tablename__ = 'LocationReportTbl'
    __table_args__ = (
        Index('LocationReportTbl_AccountId', 'AccountId'),
        Index('LocationReportTbl_DeviceTypeId', 'DeviceTypeId'),
        Index('LocationReportTbl_LocationId', 'LocationId'),
        Index('LocationReportTbl_ReportGenerated', 'ReportGenerated')
    )

    LocationReportId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LocationId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    ReportGenerated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    DeviceCount: Mapped[int] = mapped_column(Integer, nullable=False)
    TotalCheckedIn: Mapped[int] = mapped_column(Integer, nullable=False)
    TotalCheckedInWithin24: Mapped[Optional[int]] = mapped_column(Integer)


class LocationTbl(Base):
    __tablename__ = 'LocationTbl'
    __table_args__ = (
        Index('LocationTbl_AccountId', 'AccountId'),
    )

    LocationId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LocationName: Mapped[str] = mapped_column(String(32), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Longitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))


class MachineqAddToResultTbl(Base):
    __tablename__ = 'MachineqAddToResultTbl'
    __table_args__ = (
        Index('MachineqAddToResultTbl_DeviceId', 'DeviceId'),
    )

    MachineqAddToResultTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeAttempted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AddedSuccessfully: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    TimeToAdd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    HttpResponseCode: Mapped[int] = mapped_column(Integer, nullable=False)


class MachineqNetworkParamsTbl(Base):
    __tablename__ = 'MachineqNetworkParamsTbl'
    __table_args__ = (
        Index('MachineqNetworkParamsTbl_LoRaNetworkId', 'LoRaNetworkId'),
    )

    MachineqNetworkParamsTbl: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LoRaNetworkId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DeviceProfile: Mapped[str] = mapped_column(String(32), nullable=False)
    ServiceProfile: Mapped[str] = mapped_column(String(32), nullable=False)
    OutputProfile: Mapped[str] = mapped_column(String(32), nullable=False)


class MopTrackCheckinsTbl(Base):
    __tablename__ = 'MopTrackCheckinsTbl'
    __table_args__ = (
        Index('MopTrackCheckinsTbl_DeviceId', 'DeviceId'),
        Index('MopTrackCheckinsTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    Rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    EncryptedData: Mapped[str] = mapped_column(String(5464), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    GatewayId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    DataSource: Mapped[Optional[int]] = mapped_column(Integer)
    Latitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Longitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))


class NetSocketNetworkStatusMessageTbl(Base):
    __tablename__ = 'NetSocketNetworkStatusMessageTbl'
    __table_args__ = (
        Index('NetSocketNetworkStatusMessageTbl_AccountId', 'AccountId'),
        Index('NetSocketNetworkStatusMessageTbl_DeviceId', 'DeviceId'),
        Index('NetSocketNetworkStatusMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    LteConnected: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SocketConnected: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    SendSuccess: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    TimeSpent: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfConnection: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    RSRQ: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    RSRP: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    NumberOfBytesSent: Mapped[int] = mapped_column(Integer, nullable=False)
    NumberOfBytesReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    WirelessTechnology: Mapped[Optional[Any]] = mapped_column(BIT(1))
    ActiveSimSlot: Mapped[Optional[Any]] = mapped_column(BIT(1))
    EarlySocketDisconnect: Mapped[Optional[Any]] = mapped_column(BIT(1))
    DnssecResolved: Mapped[Optional[Any]] = mapped_column(BIT(1))
    Band: Mapped[Optional[int]] = mapped_column(Integer)
    EnergyEstimate: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkId: Mapped[Optional[int]] = mapped_column(Integer)


class NurBeaconScanMsgTbl(Base):
    __tablename__ = 'NurBeaconScanMsgTbl'
    __table_args__ = (
        Index('NurBeaconScanMsgTbl_AccountId', 'AccountId'),
        Index('NurBeaconScanMsgTbl_DeviceId', 'DeviceId'),
        Index('NurBeaconScanMsgTbl_NetworkTimeReceived', 'NetworkTimeReceived'),
        Index('NurBeaconScanMsgTbl_ScanEvent', 'ScanEvent'),
        Index('NurBeaconScanMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    ScanEvent: Mapped[int] = mapped_column(Integer, nullable=False)
    BeaconId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AvgRssi: Mapped[int] = mapped_column(Integer, nullable=False)
    NumRx: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurBleBeaconConfigMsgTbl(Base):
    __tablename__ = 'NurBleBeaconConfigMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('NurBleBeaconConfigMsgTbl_AccountId', 'AccountId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    BeaconPeriod: Mapped[int] = mapped_column(Integer, nullable=False)
    BeaconDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    BeaconPower: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class NurBleConfigMsgTbl(Base):
    __tablename__ = 'NurBleConfigMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('NurBleConfigMsgTbl_AccountId', 'AccountId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    BeaconScanDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    MaxSatLocTime: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsEarlyIndoorEn: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsEarlyIndoorAlwaysEn: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    MinNumSat: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class NurBootMessageTbl(Base):
    __tablename__ = 'NurBootMessageTbl'
    __table_args__ = (
        Index('NurBootMessageTbl_DeviceId', 'DeviceId'),
        Index('NurBootMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    ExceptionVector: Mapped[int] = mapped_column(Integer, nullable=False)
    BootReason: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurCatBootMessageTbl(Base):
    __tablename__ = 'NurCatBootMessageTbl'
    __table_args__ = (
        Index('NurCatBootMessageTbl_AccountId', 'AccountId'),
        Index('NurCatBootMessageTbl_DeviceId', 'DeviceId'),
        Index('NurCatBootMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    BootReason: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class NurCatFirmwareMessageTbl(Base):
    __tablename__ = 'NurCatFirmwareMessageTbl'
    __table_args__ = (
        Index('NurCatFirmwareMessageTbl_AccountId', 'AccountId'),
        Index('NurCatFirmwareMessageTbl_DeviceId', 'DeviceId'),
        Index('NurCatFirmwareMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    BootloaderVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    ApplicationVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class NurCatKeysTbl(Base):
    __tablename__ = 'NurCatKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class NurCatLastNonceTbl(Base):
    __tablename__ = 'NurCatLastNonceTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LastNonce: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)


class NurCatPositionMessageTbl(Base):
    __tablename__ = 'NurCatPositionMessageTbl'
    __table_args__ = (
        Index('NurCatPositionMessageTbl_AccountId', 'AccountId'),
        Index('NurCatPositionMessageTbl_DeviceId', 'DeviceId'),
        Index('NurCatPositionMessageTbl_TimeOfFix', 'TimeOfFix'),
        Index('NurCatPositionMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AltitudeGps: Mapped[int] = mapped_column(Integer, nullable=False)
    BatteryVoltage: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class NurConfigurationMessageTbl(Base):
    __tablename__ = 'NurConfigurationMessageTbl'
    __table_args__ = (
        Index('NurConfigurationMessageTbl_DeviceId', 'DeviceId'),
        Index('NurConfigurationMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    AccThresh: Mapped[int] = mapped_column(Integer, nullable=False)
    AccDur: Mapped[int] = mapped_column(Integer, nullable=False)
    StopMotionWait: Mapped[int] = mapped_column(Integer, nullable=False)
    HeartBeat: Mapped[int] = mapped_column(Integer, nullable=False)
    GpsTtf: Mapped[int] = mapped_column(Integer, nullable=False)
    ContMotionWait: Mapped[int] = mapped_column(Integer, nullable=False)
    AccThreshDis: Mapped[int] = mapped_column(Integer, nullable=False)
    AccDurDis: Mapped[int] = mapped_column(Integer, nullable=False)
    StopMotionWaitDis: Mapped[int] = mapped_column(Integer, nullable=False)
    AccSettings: Mapped[int] = mapped_column(Integer, nullable=False)
    AccPoll: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurFirmwareMessageTbl(Base):
    __tablename__ = 'NurFirmwareMessageTbl'
    __table_args__ = (
        Index('NurFirmwareMessageTbl_DeviceId', 'DeviceId'),
        Index('NurFirmwareMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    FirmwareVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    BootloaderVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    FuotaVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    NumberReceivedFuotaPackets: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    MulticastConfigCrc: Mapped[Optional[int]] = mapped_column(Integer)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurHardwareFailuresMessageTbl(Base):
    __tablename__ = 'NurHardwareFailuresMessageTbl'
    __table_args__ = (
        Index('NurHardwareFailuresMessageTbl_DeviceId', 'DeviceId'),
        Index('NurHardwareFailuresMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    GpsFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    AccelerometerFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    ExternalFlashFailures: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurIndoorLocConfigMsgTbl(Base):
    __tablename__ = 'NurIndoorLocConfigMsgTbl'
    __table_args__ = (
        Index('NurIndoorLocConfigMsgTbl_AccountId', 'AccountId'),
        Index('NurIndoorLocConfigMsgTbl_DeviceId', 'DeviceId'),
        Index('NurIndoorLocConfigMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NumberOfSends: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeBetweenSends: Mapped[int] = mapped_column(Integer, nullable=False)
    MaxTimeSatLock: Mapped[int] = mapped_column(Integer, nullable=False)
    IsEarlyIndoorEn: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsEarlyIndoorAlwaysEn: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    MinNumSat: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurIndoorLocMsgTbl(Base):
    __tablename__ = 'NurIndoorLocMsgTbl'
    __table_args__ = (
        Index('NurIndoorLocMsgTbl_AccountId', 'AccountId'),
        Index('NurIndoorLocMsgTbl_DevAddr', 'DevAddr'),
        Index('NurIndoorLocMsgTbl_DeviceId', 'DeviceId'),
        Index('NurIndoorLocMsgTbl_EventNum', 'EventNum')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    EventNum: Mapped[int] = mapped_column(Integer, nullable=False)
    PacketCounter: Mapped[int] = mapped_column(Integer, nullable=False)
    IsFinal: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    DevAddr: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurIndoorLocV2MsgTbl(Base):
    __tablename__ = 'NurIndoorLocV2MsgTbl'
    __table_args__ = (
        Index('NurIndoorLocV2MsgTbl_AccountId', 'AccountId'),
        Index('NurIndoorLocV2MsgTbl_Crc', 'Crc'),
        Index('NurIndoorLocV2MsgTbl_DeviceId', 'DeviceId'),
        Index('NurIndoorLocV2MsgTbl_NetworkTimeReceived', 'NetworkTimeReceived'),
        Index('NurIndoorLocV2MsgTbl_ScanEvent', 'ScanEvent'),
        Index('NurIndoorLocV2MsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    ScanEvent: Mapped[int] = mapped_column(Integer, nullable=False)
    NumberOfBeacons: Mapped[int] = mapped_column(Integer, nullable=False)
    ScanTime: Mapped[int] = mapped_column(Integer, nullable=False)
    Battery: Mapped[int] = mapped_column(Integer, nullable=False)
    Temperature: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    TimeInMotion: Mapped[int] = mapped_column(Integer, nullable=False)
    Crc: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurJumpTrack95MessageTbl(Base):
    __tablename__ = 'NurJumpTrack95MessageTbl'
    __table_args__ = (
        Index('NurJumpTrack95MessageTbl_AccountId', 'AccountId'),
        Index('NurJumpTrack95MessageTbl_DeviceId', 'DeviceId'),
        Index('NurJumpTrack95MessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    AltitudeGps: Mapped[int] = mapped_column(Integer, nullable=False)
    BatteryVoltage: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurKeysArchiveTbl(Base):
    __tablename__ = 'NurKeysArchiveTbl'
    __table_args__ = (
        Index('NurKeysArchiveTbl_DeviceId', 'DeviceId'),
    )

    NurKeysArchiveTblId: Mapped[int] = mapped_column(Integer, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AppEui: Mapped[int] = mapped_column(BigInteger, nullable=False)
    AppSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKey: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    NetSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKey: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    DateTimeArchivedUtc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class NurKeysTbl(Base):
    __tablename__ = 'NurKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    AppSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKey: Mapped[str] = mapped_column(String(44), nullable=False)
    AppKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    NetSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKey: Mapped[str] = mapped_column(String(44), nullable=False)
    NetKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    AppEui: Mapped[int] = mapped_column(BigInteger, nullable=False)


class NurPositionMessageTbl(Base):
    __tablename__ = 'NurPositionMessageTbl'
    __table_args__ = (
        Index('NurPositionMessageTbl_DeviceId', 'DeviceId'),
        Index('NurPositionMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    State: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    Battery: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAssociated: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsIndoor: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurPositionV2MsgTbl(Base):
    __tablename__ = 'NurPositionV2MsgTbl'
    __table_args__ = (
        Index('NurPositionV2MsgTbl_AccountId', 'AccountId'),
        Index('NurPositionV2MsgTbl_Crc', 'Crc'),
        Index('NurPositionV2MsgTbl_DeviceId', 'DeviceId'),
        Index('NurPositionV2MsgTbl_TimeOfFix', 'TimeOfFix')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    Battery: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAssociated: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsUsingGpsAiding: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Temperature: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeInMotion: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    Crc: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class NurStartMotionCnfgMsgTbl(Base):
    __tablename__ = 'NurStartMotionCnfgMsgTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('NurStartMotionCnfgMsgTbl_AccountId', 'AccountId'),
        Index('NurStartMotionCnfgMsgTbl_TimeReceived', 'TimeReceived')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    StartMotionWindowStart: Mapped[int] = mapped_column(Integer, nullable=False)
    StartMotionWindowEnd: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class NurStartMotionMsgTbl(Base):
    __tablename__ = 'NurStartMotionMsgTbl'
    __table_args__ = (
        Index('NurStartMotionMsgTbl_AccountId', 'AccountId'),
        Index('NurStartMotionMsgTbl_DeviceId', 'DeviceId'),
        Index('NurStartMotionMsgTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    MultiCrc: Mapped[Optional[int]] = mapped_column(Integer)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class PositionMessageTankTrackTbl(Base):
    __tablename__ = 'PositionMessageTankTrackTbl'
    __table_args__ = (
        Index('PositionMessageTankTrackTbl_DeviceId', 'DeviceId'),
        Index('PositionMessageTankTrackTbl_TimeOfFix', 'TimeOfFix'),
        Index('PositionMessageTankTrackTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsGpsIndoors: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfFix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class PowerINA219MessageICLETbl(Base):
    __tablename__ = 'PowerINA219MessageICLETbl'
    __table_args__ = (
        Index('PowerINA219MessageICLETbl_DeviceId', 'DeviceId'),
        Index('PowerINA219MessageICLETbl_TimeReceived', 'TimeReceived')
    )

    CheckInId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Nonce: Mapped[int] = mapped_column(Integer, nullable=False)
    PowerPort: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfFirstMeasurement: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    BusVoltage: Mapped[float] = mapped_column(Float, nullable=False)
    ShuntVoltage: Mapped[float] = mapped_column(Float, nullable=False)
    NumberOfSamples: Mapped[int] = mapped_column(Integer, nullable=False)
    Ina219Config: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class RatFuckTbl(Base):
    __tablename__ = 'RatFuckTbl'

    RatFuckId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    RatFuck: Mapped[str] = mapped_column(String(32), nullable=False)


class RelayMessageICLETbl(Base):
    __tablename__ = 'RelayMessageICLETbl'
    __table_args__ = (
        Index('RelayMessageICLETbl_DeviceId', 'DeviceId'),
        Index('RelayMessageICLETbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    RelayPort: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeActuated: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    EventDuration: Mapped[int] = mapped_column(Integer, nullable=False)
    ActuationType: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class ScratchPadMsgTbl(Base):
    __tablename__ = 'ScratchPadMsgTbl'
    __table_args__ = (
        Index('ScratchPadMsgTbl_DeviceId', 'DeviceId'),
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    MsgPayload: Mapped[Optional[str]] = mapped_column(String(771))


class StartMotionMessageTankTrackTbl(Base):
    __tablename__ = 'StartMotionMessageTankTrackTbl'
    __table_args__ = (
        Index('StartMotionMessageTankTrackTbl_DeviceId', 'DeviceId'),
        Index('StartMotionMessageTankTrackTbl_TimeOfMovement', 'TimeOfMovement'),
        Index('StartMotionMessageTankTrackTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    AccThresh: Mapped[int] = mapped_column(Integer, nullable=False)
    AccDur: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfMovement: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class SystemEndpointsMapTbl(Base):
    __tablename__ = 'SystemEndpointsMapTbl'
    __table_args__ = (
        Index('SystemEndpointsMapTbl_AccountId', 'AccountId'),
        Index('SystemEndpointsMapTbl_DeviceTypeId', 'DeviceTypeId')
    )

    SystemEndpointMapId: Mapped[int] = mapped_column(Integer, primary_key=True)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    EndpointId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    IsActive: Mapped[Any] = mapped_column(BIT(1), nullable=False)


class TankLevelMessageTankTrackTbl(Base):
    __tablename__ = 'TankLevelMessageTankTrackTbl'
    __table_args__ = (
        Index('TankLevelMessageTankTrackTbl_DeviceId', 'DeviceId'),
        Index('TankLevelMessageTankTrackTbl_TimeOfMeasurement', 'TimeOfMeasurement'),
        Index('TankLevelMessageTankTrackTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    Tank1Level: Mapped[int] = mapped_column(Integer, nullable=False)
    Tank1Alarm: Mapped[int] = mapped_column(Integer, nullable=False)
    Tank2Level: Mapped[int] = mapped_column(Integer, nullable=False)
    Tank2Alarm: Mapped[int] = mapped_column(Integer, nullable=False)
    BatteryVoltage: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeOfMeasurement: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class TankTrackKeysTbl(Base):
    __tablename__ = 'TankTrackKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class TankTrackLastNonceTbl(Base):
    __tablename__ = 'TankTrackLastNonceTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    LastNonce: Mapped[int] = mapped_column(Integer, nullable=False)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)


class TektelicAddToResultTbl(Base):
    __tablename__ = 'TektelicAddToResultTbl'
    __table_args__ = (
        Index('TektelicAddToResultTbl_DeviceId', 'DeviceId'),
    )

    TektelicAddToResultTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeAttempted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    AddedSuccessfully: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    TimeToAdd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    HttpResponseCode: Mapped[int] = mapped_column(Integer, nullable=False)


class TektelicApiAccountsTbl(Base):
    __tablename__ = 'TektelicApiAccountsTbl'
    __table_args__ = (
        Index('TektelicApiAccountsTblId', 'TektelicApiAccountsTblId'),
    )

    TektelicApiAccountsTblId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ClientId: Mapped[Optional[str]] = mapped_column(String(255))
    Secret: Mapped[Optional[str]] = mapped_column(String(255))


class TektelicNetworkParamsTbl(Base):
    __tablename__ = 'TektelicNetworkParamsTbl'
    __table_args__ = (
        Index('LoRaNetworkId', 'LoRaNetworkId', unique=True),
    )

    TektelicNetworkParamsTbl: Mapped[int] = mapped_column(Integer, primary_key=True)
    LoRaNetworkId: Mapped[Optional[int]] = mapped_column(BigInteger)
    ApplicationId: Mapped[Optional[str]] = mapped_column(String(40))
    ApplicationName: Mapped[Optional[str]] = mapped_column(String(255))
    CustomerId: Mapped[Optional[str]] = mapped_column(String(40))
    CustomerName: Mapped[Optional[str]] = mapped_column(String(255))


class TestDevicePositionMessageTbl(Base):
    __tablename__ = 'TestDevicePositionMessageTbl'
    __table_args__ = (
        Index('NurPositionMessageTbl_DeviceId', 'DeviceId'),
        Index('NurPositionMessageTbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    State: Mapped[int] = mapped_column(Integer, nullable=False)
    Latitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Longitude: Mapped[decimal.Decimal] = mapped_column(Double(asdecimal=True), nullable=False)
    Ttf: Mapped[int] = mapped_column(Integer, nullable=False)
    Accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    Battery: Mapped[int] = mapped_column(Integer, nullable=False)
    IsAssociated: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsValidGpsFix: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsIndoor: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    IsInMotion: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    UpdateReason: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)
    FCntUp: Mapped[Optional[int]] = mapped_column(Integer)
    FCntDn: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayLat: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayLon: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewayId: Mapped[Optional[str]] = mapped_column(String(16))
    GatewayCount: Mapped[Optional[int]] = mapped_column(Integer)
    GatewayRssi: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    GatewaySnr: Mapped[Optional[decimal.Decimal]] = mapped_column(Double(asdecimal=True))
    Channel: Mapped[Optional[str]] = mapped_column(String(4))
    SpreadingFactor: Mapped[Optional[int]] = mapped_column(Integer)
    NetworkTimeReceived: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class TimeRequestIdentifierTbl(Base):
    __tablename__ = 'TimeRequestIdentifierTbl'
    __table_args__ = (
        Index('DeviceId', 'DeviceId', unique=True),
        Index('IX_TimeRequestIdentifierTbl_DeviceTypeId', 'DeviceTypeId')
    )

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceTypeId: Mapped[int] = mapped_column(Integer, nullable=False)


class TimeRequestMessageTbl(Base):
    __tablename__ = 'TimeRequestMessageTbl'
    __table_args__ = (
        Index('TimeRequestMessageTbl_DeviceId', 'DeviceId'),
    )

    TimeRequestMessageId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeRequestId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeSinceBoot: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class TimeResponseMessageTbl(Base):
    __tablename__ = 'TimeResponseMessageTbl'
    __table_args__ = (
        Index('TimeResponseMessageTbl_DeviceId', 'DeviceId'),
    )

    TimeResponseMessageId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    NonceReceived: Mapped[int] = mapped_column(Integer, nullable=False)
    TimeResponse: Mapped[datetime.datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class Track02Tbl(Base):
    __tablename__ = 'Track02Tbl'
    __table_args__ = (
        Index('Track02Tbl_DeviceId', 'DeviceId'),
        Index('Track02Tbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    DeviceIdentifier: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeSinceBoot: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class Track04Tbl(Base):
    __tablename__ = 'Track04Tbl'
    __table_args__ = (
        Index('Track04Tbl_DeviceId', 'DeviceId'),
        Index('Track04Tbl_TimeReceived', 'TimeReceived')
    )

    CheckinId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    DeviceId: Mapped[int] = mapped_column(BigInteger, nullable=False)
    TimeReceived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    FromDevice: Mapped[Any] = mapped_column(BIT(1), nullable=False)
    Flags: Mapped[int] = mapped_column(Integer, nullable=False)
    FirmwareVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    AccountId: Mapped[int] = mapped_column(Integer, nullable=False)


class TrackKeysTbl(Base):
    __tablename__ = 'TrackKeysTbl'

    DeviceId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    EncSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKey: Mapped[str] = mapped_column(String(44), nullable=False)
    EncKeyId: Mapped[int] = mapped_column(Integer, nullable=False)
    MicSalt: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKey: Mapped[str] = mapped_column(String(44), nullable=False)
    MicKeyId: Mapped[int] = mapped_column(Integer, nullable=False)


class UtilityEndpointsTbl(Base):
    __tablename__ = 'UtilityEndpointsTbl'

    UtilityEndpointTblId: Mapped[int] = mapped_column(Integer, primary_key=True)
    UtilityName: Mapped[str] = mapped_column(String(64), nullable=False)
    EndpointId: Mapped[int] = mapped_column(BigInteger, nullable=False)

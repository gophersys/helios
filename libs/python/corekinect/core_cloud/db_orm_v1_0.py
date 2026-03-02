from typing import Optional
import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Double, ForeignKeyConstraint, Identity, Index, Integer, PrimaryKeyConstraint, SmallInteger, String, Table, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Accountshistorytbl(Base):
    __tablename__ = 'accountshistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='accountshistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    isactive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str] = mapped_column(String(64), nullable=False)


class Accountstbl(Base):
    __tablename__ = 'accountstbl'
    __table_args__ = (
        PrimaryKeyConstraint('accountid', name='accountstbl_pkey'),
    )

    accountid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    isactive: Mapped[bool] = mapped_column(Boolean, nullable=False)

    apikeystbl: Mapped[list['Apikeystbl']] = relationship('Apikeystbl', back_populates='accountstbl')
    devicestbl: Mapped[list['Devicestbl']] = relationship('Devicestbl', back_populates='accountstbl')
    loginstbl: Mapped[list['Loginstbl']] = relationship('Loginstbl', back_populates='accountstbl')
    webhookstbl: Mapped[list['Webhookstbl']] = relationship('Webhookstbl', back_populates='accountstbl')


class Configbeaconhistorytbl(Base):
    __tablename__ = 'configbeaconhistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configbeaconhistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    isenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    isbeacon: Mapped[bool] = mapped_column(Boolean, nullable=False)
    beaconper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    beacondur: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    beaconpwr: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sessionkeycrc: Mapped[int] = mapped_column(Integer, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configbiometrichistorytbl(Base):
    __tablename__ = 'configbiometrichistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configbiometrichistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    forcecheckin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lowriskstatereportperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    increasedriskhsithreshold: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    increasedriskstatereportperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    emergencyhsithreshold: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    emergencystatereportperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configdronemodehistorytbl(Base):
    __tablename__ = 'configdronemodehistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configdronemodehistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ondronepositionperiod: Mapped[int] = mapped_column(Integer, nullable=False)
    dronecheckperiod: Mapped[int] = mapped_column(Integer, nullable=False)
    hifreqpsdbin: Mapped[int] = mapped_column(Integer, nullable=False)
    hifreqondronepercentage: Mapped[int] = mapped_column(Integer, nullable=False)
    psdsumthreshold: Mapped[int] = mapped_column(Integer, nullable=False)
    uploadpsd: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accelerometersamplerate: Mapped[int] = mapped_column(Integer, nullable=False)
    numaxes: Mapped[int] = mapped_column(Integer, nullable=False)
    nenter: Mapped[int] = mapped_column(Integer, nullable=False)
    nexit: Mapped[int] = mapped_column(Integer, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configemergencyv2historytbl(Base):
    __tablename__ = 'configemergencyv2historytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configemergencyv2historytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timelimit: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    btnactivationtime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    btntimeout: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configfallhistorytbl(Base):
    __tablename__ = 'configfallhistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configfallhistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    isjumpmodeenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    jumpstategpsper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    jumpstatedur: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    xlrfreefallthresh: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    xlrfreefalldur: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    altchangefreefalltrigger: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    altchangejumptrigger: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stablealtnumsamples: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stablealtthresh: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configgpshistorytbl(Base):
    __tablename__ = 'configgpshistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configgpshistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ispsmenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    aidingenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gnssupdatefreq: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    targetfixaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    targetfixpdop: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configgroundhistorytbl(Base):
    __tablename__ = 'configgroundhistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configgroundhistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gpshbper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    contmotionper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stopmotiontimeout: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hbacqtimeout: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motionacqtimeout: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motionthresh: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motiondur: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    startmotionwinstart: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    startmotionwinend: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motionacquisitionontime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motioninitialacquisitionontime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Confighipshistorytbl(Base):
    __tablename__ = 'confighipshistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='confighipshistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mode: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    scanconstantly: Mapped[bool] = mapped_column(Boolean, nullable=False)
    forcecheckin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reportper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    groupcode: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sourceuserid: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configlorahistorytbl(Base):
    __tablename__ = 'configlorahistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configlorahistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    isloraenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sessioncrc: Mapped[int] = mapped_column(Integer, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configmodemhistorytbl(Base):
    __tablename__ = 'configmodemhistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='configmodemhistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shortbackofftime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    normalbackofftime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    longbackofftime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    registrationtimeoutperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    socketconnectiontimeoutperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    connectionfailurethreshold: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sockettimeoutperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Deviceaccounthistorytbl(Base):
    __tablename__ = 'deviceaccounthistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='deviceaccounthistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Devicefirmwarehistorytbl(Base):
    __tablename__ = 'devicefirmwarehistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='devicefirmwarehistorytbl_pkey'),
        Index('idx_devicefirmwarehistorytbl_deviceid', 'deviceid')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    appid: Mapped[int] = mapped_column(Integer, nullable=False)
    majorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    minorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    releasetrack: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ismfg: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Devicemessagestbl(Base):
    __tablename__ = 'devicemessagestbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='devicemessagestbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    isuplink: Mapped[bool] = mapped_column(Boolean, nullable=False)
    interfacetype: Mapped[int] = mapped_column(Integer, nullable=False)
    timeofrecord: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    messageid: Mapped[int] = mapped_column(Integer, nullable=False)
    messageuid: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))

    devicedatausagetbl: Mapped[list['Devicedatausagetbl']] = relationship('Devicedatausagetbl', foreign_keys='[Devicedatausagetbl.firstrecordid]', back_populates='devicemessagestbl')
    devicedatausagetbl_: Mapped[list['Devicedatausagetbl']] = relationship('Devicedatausagetbl', foreign_keys='[Devicedatausagetbl.lastrecordid]', back_populates='devicemessagestbl_')


class Deviceprofilestbl(Base):
    __tablename__ = 'deviceprofilestbl'
    __table_args__ = (
        PrimaryKeyConstraint('deviceid', name='deviceprofilestbl_pkey'),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    publickeycipher: Mapped[str] = mapped_column(String(256), nullable=False)
    publickeytype: Mapped[int] = mapped_column(Integer, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Devicetransferhistorytbl(Base):
    __tablename__ = 'devicetransferhistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='devicetransferhistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    targetid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    isacked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timesenttodevice: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    timereturnedtoserver: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Devicetransfertargetstbl(Base):
    __tablename__ = 'devicetransfertargetstbl'
    __table_args__ = (
        PrimaryKeyConstraint('targetid', name='devicetransfertargetstbl_pkey'),
    )

    targetid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    timeserverpublickey: Mapped[str] = mapped_column(String(256), nullable=False)
    serverbaseurl: Mapped[str] = mapped_column(String(256), nullable=False)
    devicerekeypath: Mapped[str] = mapped_column(String(128), nullable=False)
    timeserverport: Mapped[int] = mapped_column(Integer, nullable=False)
    sessiongenerationserverport: Mapped[int] = mapped_column(Integer, nullable=False)
    dataserverport: Mapped[int] = mapped_column(Integer, nullable=False)
    requirednssec: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    devicetransferstbl: Mapped[list['Devicetransferstbl']] = relationship('Devicetransferstbl', back_populates='devicetransfertargetstbl')


class Devicetypevarianttbl(Base):
    __tablename__ = 'devicetypevarianttbl'
    __table_args__ = (
        PrimaryKeyConstraint('devicetypeid', 'devicevariantid', name='devicetypevarianttbl_pkey'),
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicetypename: Mapped[str] = mapped_column(String(128), nullable=False)

    devicefirmwareappidstbl: Mapped[list['Devicefirmwareappidstbl']] = relationship('Devicefirmwareappidstbl', back_populates='devicetypevarianttbl')
    devicestbl: Mapped[list['Devicestbl']] = relationship('Devicestbl', back_populates='devicetypevarianttbl')
    fuotaplanstbl: Mapped[list['Fuotaplanstbl']] = relationship('Fuotaplanstbl', back_populates='devicetypevarianttbl')
    webhooksperdevicetypetbl: Mapped[list['Webhooksperdevicetypetbl']] = relationship('Webhooksperdevicetypetbl', back_populates='devicetypevarianttbl')
    fuotasettingsperdevicetypetbl: Mapped[list['Fuotasettingsperdevicetypetbl']] = relationship('Fuotasettingsperdevicetypetbl', back_populates='devicetypevarianttbl')


class Fuotaprogresshistorytbl(Base):
    __tablename__ = 'fuotaprogresshistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='fuotaprogresshistorytbl_pkey'),
        Index('idx_fuotaprogresshistorytbl_deviceid', 'deviceid')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    appid: Mapped[int] = mapped_column(Integer, nullable=False)
    majorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    minorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    releasetrack: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ismfg: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pagesapplied: Mapped[int] = mapped_column(Integer, nullable=False)
    totalpages: Mapped[int] = mapped_column(Integer, nullable=False)
    timestarted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timefinished: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Fuotaprogresstbl(Base):
    __tablename__ = 'fuotaprogresstbl'
    __table_args__ = (
        PrimaryKeyConstraint('deviceid', 'appid', name='fuotaprogresstbl_pkey'),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    majorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    minorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    releasetrack: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ismfg: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pagesapplied: Mapped[int] = mapped_column(Integer, nullable=False)
    totalpages: Mapped[int] = mapped_column(Integer, nullable=False)
    timestarted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastupdated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Fuotasettingsperdevicehistorytbl(Base):
    __tablename__ = 'fuotasettingsperdevicehistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='fuotasettingsperdevicehistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    planid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    enablefuota: Mapped[bool] = mapped_column(Boolean, nullable=False)
    maxstage: Mapped[int] = mapped_column(Integer, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Fuotasettingsperdevicetypehistorytbl(Base):
    __tablename__ = 'fuotasettingsperdevicetypehistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('recordid', name='fuotasettingsperdevicetypehistorytbl_pkey'),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    devicetypeid: Mapped[int] = mapped_column(Integer, nullable=False)
    devicevariantid: Mapped[int] = mapped_column(Integer, nullable=False)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    planid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    enablefuota: Mapped[bool] = mapped_column(Boolean, nullable=False)
    maxstage: Mapped[int] = mapped_column(Integer, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Permissionstbl(Base):
    __tablename__ = 'permissionstbl'
    __table_args__ = (
        PrimaryKeyConstraint('permissionid', name='permissionstbl_pkey'),
        UniqueConstraint('permissionkey', name='permissionstbl_permissionkey_key')
    )

    permissionid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    permissionkey: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)

    rolestbl: Mapped[list['Rolestbl']] = relationship('Rolestbl', secondary='rolepermissiongrantstbl', back_populates='permissionstbl')
    loginpermissiongrantshistorytbl: Mapped[list['Loginpermissiongrantshistorytbl']] = relationship('Loginpermissiongrantshistorytbl', back_populates='permissionstbl')
    loginpermissiongrantstbl: Mapped[list['Loginpermissiongrantstbl']] = relationship('Loginpermissiongrantstbl', back_populates='permissionstbl')


class Rolestbl(Base):
    __tablename__ = 'rolestbl'
    __table_args__ = (
        PrimaryKeyConstraint('roleid', name='rolestbl_pkey'),
        UniqueConstraint('rolekey', name='rolestbl_rolekey_key')
    )

    roleid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rolekey: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)

    permissionstbl: Mapped[list['Permissionstbl']] = relationship('Permissionstbl', secondary='rolepermissiongrantstbl', back_populates='rolestbl')
    rolestbl: Mapped[list['Rolestbl']] = relationship('Rolestbl', secondary='roleinheritancetbl', primaryjoin=lambda: Rolestbl.roleid == t_roleinheritancetbl.c.childroleid, secondaryjoin=lambda: Rolestbl.roleid == t_roleinheritancetbl.c.parentroleid, back_populates='rolestbl_')
    rolestbl_: Mapped[list['Rolestbl']] = relationship('Rolestbl', secondary='roleinheritancetbl', primaryjoin=lambda: Rolestbl.roleid == t_roleinheritancetbl.c.parentroleid, secondaryjoin=lambda: Rolestbl.roleid == t_roleinheritancetbl.c.childroleid, back_populates='rolestbl')
    loginrolegrantshistorytbl: Mapped[list['Loginrolegrantshistorytbl']] = relationship('Loginrolegrantshistorytbl', back_populates='rolestbl')
    loginrolegrantstbl: Mapped[list['Loginrolegrantstbl']] = relationship('Loginrolegrantstbl', back_populates='rolestbl')


class Schemaversions(Base):
    __tablename__ = 'schemaversions'
    __table_args__ = (
        PrimaryKeyConstraint('schemaversionsid', name='PK_schemaversions_Id'),
    )

    schemaversionsid: Mapped[int] = mapped_column(Integer, primary_key=True)
    scriptname: Mapped[str] = mapped_column(String(255), nullable=False)
    applied: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Webhooksperdevicehistorytbl(Base):
    __tablename__ = 'webhooksperdevicehistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('deviceid', 'webhookid', 'unassignedat', name='webhooksperdevicehistorytbl_pkey'),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    webhookid: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignedat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    unassignedat: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)


class Webhooksperdevicetbl(Base):
    __tablename__ = 'webhooksperdevicetbl'
    __table_args__ = (
        PrimaryKeyConstraint('deviceid', 'webhookid', name='webhooksperdevicetbl_pkey'),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    webhookid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    assignedat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)


class Webhooksperdevicetypehistorytbl(Base):
    __tablename__ = 'webhooksperdevicetypehistorytbl'
    __table_args__ = (
        PrimaryKeyConstraint('devicetypeid', 'devicevariantid', 'unassignedat', name='webhooksperdevicetypehistorytbl_pkey'),
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhookid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assignedat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    unassignedat: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)


class Apikeystbl(Base):
    __tablename__ = 'apikeystbl'
    __table_args__ = (
        ForeignKeyConstraint(['accountid'], ['accountstbl.accountid'], name='fk_accountstbl_id'),
        PrimaryKeyConstraint('id', name='apikeystbl_pkey')
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    description: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    isactive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    datetimeissued: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    datetimerevoked: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    revocationreason: Mapped[Optional[str]] = mapped_column(String(128))

    accountstbl: Mapped['Accountstbl'] = relationship('Accountstbl', back_populates='apikeystbl')


class Devicedatausagetbl(Base):
    __tablename__ = 'devicedatausagetbl'
    __table_args__ = (
        ForeignKeyConstraint(['firstrecordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_first_id'),
        ForeignKeyConstraint(['lastrecordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_last_id'),
        PrimaryKeyConstraint('dayid', 'deviceid', name='devicedatausagetbl_pkey')
    )

    dayid: Mapped[int] = mapped_column(Integer, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    interfacetype: Mapped[int] = mapped_column(Integer, nullable=False)
    bytesreceived: Mapped[int] = mapped_column(Integer, nullable=False)
    bytessent: Mapped[int] = mapped_column(Integer, nullable=False)
    firstrecordid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lastrecordid: Mapped[int] = mapped_column(BigInteger, nullable=False)

    devicemessagestbl: Mapped['Devicemessagestbl'] = relationship('Devicemessagestbl', foreign_keys=[firstrecordid], back_populates='devicedatausagetbl')
    devicemessagestbl_: Mapped['Devicemessagestbl'] = relationship('Devicemessagestbl', foreign_keys=[lastrecordid], back_populates='devicedatausagetbl_')


class Devicefirmwareappidstbl(Base):
    __tablename__ = 'devicefirmwareappidstbl'
    __table_args__ = (
        ForeignKeyConstraint(['devicetypeid', 'devicevariantid'], ['devicetypevarianttbl.devicetypeid', 'devicetypevarianttbl.devicevariantid'], name='fk_devicetype'),
        PrimaryKeyConstraint('devicetypeid', 'devicevariantid', 'appid', name='devicefirmwareappidstbl_pkey')
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    isauxiliary: Mapped[bool] = mapped_column(Boolean, nullable=False)

    devicetypevarianttbl: Mapped['Devicetypevarianttbl'] = relationship('Devicetypevarianttbl', back_populates='devicefirmwareappidstbl')


class Devicestbl(Base):
    __tablename__ = 'devicestbl'
    __table_args__ = (
        ForeignKeyConstraint(['accountid'], ['accountstbl.accountid'], name='fk_accountstbl_id'),
        ForeignKeyConstraint(['devicetypeid', 'devvariantid'], ['devicetypevarianttbl.devicetypeid', 'devicetypevarianttbl.devicevariantid'], name='fk_devicetype'),
        PrimaryKeyConstraint('deviceid', name='devicestbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    devicetypeid: Mapped[int] = mapped_column(Integer, nullable=False)
    devvariantid: Mapped[int] = mapped_column(Integer, nullable=False)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    isactive: Mapped[bool] = mapped_column(Boolean, nullable=False)

    accountstbl: Mapped['Accountstbl'] = relationship('Accountstbl', back_populates='devicestbl')
    devicetypevarianttbl: Mapped['Devicetypevarianttbl'] = relationship('Devicetypevarianttbl', back_populates='devicestbl')
    binaryimageuploadstbl: Mapped[list['Binaryimageuploadstbl']] = relationship('Binaryimageuploadstbl', back_populates='devicestbl')
    devicefirmwarecurrenttbl: Mapped[list['Devicefirmwarecurrenttbl']] = relationship('Devicefirmwarecurrenttbl', back_populates='devicestbl')
    socketserversessionstbl: Mapped['Socketserversessionstbl'] = relationship('Socketserversessionstbl', uselist=False, back_populates='devicestbl')


class Fuotaplanstbl(Base):
    __tablename__ = 'fuotaplanstbl'
    __table_args__ = (
        ForeignKeyConstraint(['devicetypeid', 'devicevariantid'], ['devicetypevarianttbl.devicetypeid', 'devicetypevarianttbl.devicevariantid'], name='fk_devicetype'),
        PrimaryKeyConstraint('planid', name='fuotaplanstbl_pkey')
    )

    planid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plandesc: Mapped[str] = mapped_column(String(256), nullable=False)
    devicetypeid: Mapped[int] = mapped_column(Integer, nullable=False)
    devicevariantid: Mapped[int] = mapped_column(Integer, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    devicetypevarianttbl: Mapped['Devicetypevarianttbl'] = relationship('Devicetypevarianttbl', back_populates='fuotaplanstbl')
    fuotaplanstagestbl: Mapped[list['Fuotaplanstagestbl']] = relationship('Fuotaplanstagestbl', back_populates='fuotaplanstbl')
    fuotaplanstagetargetstbl: Mapped[list['Fuotaplanstagetargetstbl']] = relationship('Fuotaplanstagetargetstbl', back_populates='fuotaplanstbl')
    fuotasettingsperdevicetbl: Mapped[list['Fuotasettingsperdevicetbl']] = relationship('Fuotasettingsperdevicetbl', back_populates='fuotaplanstbl')
    fuotasettingsperdevicetypetbl: Mapped[list['Fuotasettingsperdevicetypetbl']] = relationship('Fuotasettingsperdevicetypetbl', back_populates='fuotaplanstbl')


class Loginstbl(Base):
    __tablename__ = 'loginstbl'
    __table_args__ = (
        ForeignKeyConstraint(['accountid'], ['accountstbl.accountid'], name='fk_accountstbl_id'),
        PrimaryKeyConstraint('loginid', name='loginstbl_pkey')
    )

    loginid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    isactive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    isprivileged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    accountstbl: Mapped['Accountstbl'] = relationship('Accountstbl', back_populates='loginstbl')
    loginpermissiongrantshistorytbl: Mapped[list['Loginpermissiongrantshistorytbl']] = relationship('Loginpermissiongrantshistorytbl', back_populates='loginstbl')
    loginpermissiongrantstbl: Mapped[list['Loginpermissiongrantstbl']] = relationship('Loginpermissiongrantstbl', back_populates='loginstbl')
    loginrolegrantshistorytbl: Mapped[list['Loginrolegrantshistorytbl']] = relationship('Loginrolegrantshistorytbl', back_populates='loginstbl')
    loginrolegrantstbl: Mapped[list['Loginrolegrantstbl']] = relationship('Loginrolegrantstbl', back_populates='loginstbl')


class Messagesalphahwfailtbl(Devicemessagestbl):
    __tablename__ = 'messagesalphahwfailtbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesalphahwfailtbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    xlrfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    altfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    gpsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bmsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    extflashfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    ppgfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    imufails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    irfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    battchargerfails: Mapped[Optional[int]] = mapped_column(SmallInteger)


class Messagesbeaconpositiontbl(Devicemessagestbl):
    __tablename__ = 'messagesbeaconpositiontbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesbeaconpositiontbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flags: Mapped[int] = mapped_column(Integer, nullable=False)
    isinmotion: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gnssfixvalid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gnssfixok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validdate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validtime: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confdate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conftime: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conftimeavail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    oncharger: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usedaiding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updatereason: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    psmstate: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    numsat: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fixtype: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    latitude: Mapped[float] = mapped_column(Double(53), nullable=False)
    longitude: Mapped[float] = mapped_column(Double(53), nullable=False)
    horizontalaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    gpsaltitude: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pressurealtitude: Mapped[int] = mapped_column(Integer, nullable=False)
    timeoffix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    groundspeed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    heading: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    airpressure: Mapped[float] = mapped_column(Double(53), nullable=False)
    pdop: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    vertaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    beaconid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rssi: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Messagesbiometricdatatbl(Devicemessagestbl):
    __tablename__ = 'messagesbiometricdatatbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesbiometricdatatbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofmeasurement: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    flags: Mapped[int] = mapped_column(Integer, nullable=False)
    airpressure: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    externaltemperature: Mapped[float] = mapped_column(Double(53), nullable=False)
    relativehumidity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    heartrate: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    heartrateconfidence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    spo2: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    spo2confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    skintemperature: Mapped[float] = mapped_column(Double(53), nullable=False)
    estimatedcoretemperature: Mapped[float] = mapped_column(Double(53), nullable=False)
    heatstrainindex: Mapped[float] = mapped_column(Double(53), nullable=False)
    wobbleindex: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    vsmontime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    heatemergencyeventid: Mapped[int] = mapped_column(Integer, nullable=False)


class Messagesblesessionkeytbl(Devicemessagestbl):
    __tablename__ = 'messagesblesessionkeytbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesblesessionkeytbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sessionkeycrc: Mapped[int] = mapped_column(Integer, nullable=False)


class Messagesboottbl(Devicemessagestbl):
    __tablename__ = 'messagesboottbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesboottbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofboot: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    flags: Mapped[int] = mapped_column(Integer, nullable=False)
    chipid: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    bootreason: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    numexceptions: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Messagescommshwfailtbl(Devicemessagestbl):
    __tablename__ = 'messagescommshwfailtbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagescommshwfailtbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    simfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    sx1262fails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    ipcfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    extflashfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    secelemfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    satmodemfails: Mapped[Optional[int]] = mapped_column(SmallInteger)


class Messagesemergencyeventresptbl(Devicemessagestbl):
    __tablename__ = 'messagesemergencyeventresptbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesemergencyeventresptbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    emergencyeventid: Mapped[int] = mapped_column(Integer, nullable=False)
    flags: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Messagesemergencypositiontbl(Devicemessagestbl):
    __tablename__ = 'messagesemergencypositiontbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesemergencypositiontbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flags: Mapped[int] = mapped_column(Integer, nullable=False)
    isinmotion: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gnssfixvalid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gnssfixok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validdate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validtime: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confdate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conftime: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conftimeavail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    oncharger: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usedaiding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updatereason: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    psmstate: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    numsat: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fixtype: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    latitude: Mapped[float] = mapped_column(Double(53), nullable=False)
    longitude: Mapped[float] = mapped_column(Double(53), nullable=False)
    gpsontime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    horizontalaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    gpsaltitude: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pressurealtitude: Mapped[int] = mapped_column(Integer, nullable=False)
    timeoffix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    groundspeed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    heading: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    battpercent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    airpressure: Mapped[float] = mapped_column(Double(53), nullable=False)
    temperature: Mapped[float] = mapped_column(Double(53), nullable=False)
    pdop: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    vertaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    emergencyeventid: Mapped[int] = mapped_column(Integer, nullable=False)


class Messagesfalleventtbl(Devicemessagestbl):
    __tablename__ = 'messagesfalleventtbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesfalleventtbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeoffall: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    flags: Mapped[int] = mapped_column(Integer, nullable=False)


class Messageshipsdatatbl(Devicemessagestbl):
    __tablename__ = 'messageshipsdatatbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messageshipsdatatbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofsample: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    groupcode: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sourceuserid: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hsidataval: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hrdataval: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    estcoretemp: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    skintemp: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    nii: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    risk: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    battery: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Messageshwfailtbl(Devicemessagestbl):
    __tablename__ = 'messageshwfailtbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messageshwfailtbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    xlrfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    altfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    gpsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    sx1262fails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    ipcfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bmsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    extflashfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    secelemfails: Mapped[Optional[int]] = mapped_column(SmallInteger)


class Messagesnetworkstatusv4tbl(Devicemessagestbl):
    __tablename__ = 'messagesnetworkstatusv4tbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesnetworkstatusv4tbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofconnection: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    didlteconn: Mapped[bool] = mapped_column(Boolean, nullable=False)
    didsockconn: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sendsuccess: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usednbiot: Mapped[bool] = mapped_column(Boolean, nullable=False)
    didusesim1: Mapped[bool] = mapped_column(Boolean, nullable=False)
    didsocketdisconnectearly: Mapped[bool] = mapped_column(Boolean, nullable=False)
    didusednssec: Mapped[bool] = mapped_column(Boolean, nullable=False)
    flags: Mapped[int] = mapped_column(Integer, nullable=False)
    timespent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rsrq: Mapped[float] = mapped_column(Double(53), nullable=False)
    rsrp: Mapped[float] = mapped_column(Double(53), nullable=False)
    bytessent: Mapped[int] = mapped_column(Integer, nullable=False)
    bytesreceived: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    energyestimate: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    networkid: Mapped[int] = mapped_column(Integer, nullable=False)


class Messagespositionv5tbl(Devicemessagestbl):
    __tablename__ = 'messagespositionv5tbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagespositionv5tbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flags: Mapped[int] = mapped_column(Integer, nullable=False)
    isinmotion: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gnssfixvalid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gnssfixok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validdate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validtime: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confdate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conftime: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conftimeavail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    oncharger: Mapped[bool] = mapped_column(Boolean, nullable=False)
    usedaiding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updatereason: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    psmstate: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    numsat: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fixtype: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    latitude: Mapped[float] = mapped_column(Double(53), nullable=False)
    longitude: Mapped[float] = mapped_column(Double(53), nullable=False)
    gpsontime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    horizontalaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    gpsaltitude: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pressurealtitude: Mapped[int] = mapped_column(Integer, nullable=False)
    timeoffix: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    groundspeed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    heading: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    battvoltage: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    airpressure: Mapped[float] = mapped_column(Double(53), nullable=False)
    temperature: Mapped[float] = mapped_column(Double(53), nullable=False)
    avgforce: Mapped[float] = mapped_column(Double(53), nullable=False)
    maxforce: Mapped[float] = mapped_column(Double(53), nullable=False)
    battpercent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pdop: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    bmstemp: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    vertaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    emergencyeventid: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))


class Messagesreboottbl(Devicemessagestbl):
    __tablename__ = 'messagesreboottbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesreboottbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commsflags: Mapped[int] = mapped_column(Integer, nullable=False)
    appflags: Mapped[int] = mapped_column(Integer, nullable=False)


class Messagesscratchpadtbl(Devicemessagestbl):
    __tablename__ = 'messagesscratchpadtbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesscratchpadtbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payload: Mapped[Optional[str]] = mapped_column(String(771))


class Messagessigma5hwfailtbl(Devicemessagestbl):
    __tablename__ = 'messagessigma5hwfailtbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagessigma5hwfailtbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    xlrfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    altfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    gpsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bmsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    extflashfails: Mapped[Optional[int]] = mapped_column(SmallInteger)


class Messagesthetahwfailtbl(Devicemessagestbl):
    __tablename__ = 'messagesthetahwfailtbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='messagesthetahwfailtbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    xlrfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    altfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    gpsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bmsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    extflashfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    battchargerfails: Mapped[Optional[int]] = mapped_column(SmallInteger)


t_roleinheritancetbl = Table(
    'roleinheritancetbl', Base.metadata,
    Column('parentroleid', BigInteger, primary_key=True),
    Column('childroleid', BigInteger, primary_key=True),
    ForeignKeyConstraint(['childroleid'], ['rolestbl.roleid'], name='fk_rolestbl_id_parent'),
    ForeignKeyConstraint(['parentroleid'], ['rolestbl.roleid'], name='fk_rolestbl_id'),
    PrimaryKeyConstraint('parentroleid', 'childroleid', name='roleinheritancetbl_pkey')
)


t_rolepermissiongrantstbl = Table(
    'rolepermissiongrantstbl', Base.metadata,
    Column('roleid', BigInteger, primary_key=True),
    Column('permissionid', BigInteger, primary_key=True),
    ForeignKeyConstraint(['permissionid'], ['permissionstbl.permissionid'], name='fk_permissionstbl_id'),
    ForeignKeyConstraint(['roleid'], ['rolestbl.roleid'], name='fk_rolestbl_id'),
    PrimaryKeyConstraint('roleid', 'permissionid', name='rolepermissiongrantstbl_pkey')
)


class Socketserver1messagestbl(Devicemessagestbl):
    __tablename__ = 'socketserver1messagestbl'
    __table_args__ = (
        ForeignKeyConstraint(['recordid'], ['devicemessagestbl.recordid'], name='fk_devicemessagestbl_id'),
        PrimaryKeyConstraint('recordid', name='socketserver1messagestbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    packetid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    didack: Mapped[bool] = mapped_column(Boolean, nullable=False)
    didnak: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Webhooksperdevicetypetbl(Base):
    __tablename__ = 'webhooksperdevicetypetbl'
    __table_args__ = (
        ForeignKeyConstraint(['devicetypeid', 'devicevariantid'], ['devicetypevarianttbl.devicetypeid', 'devicetypevarianttbl.devicevariantid'], name='fk_devicetype'),
        PrimaryKeyConstraint('devicetypeid', 'devicevariantid', 'webhookid', name='webhooksperdevicetypetbl_pkey')
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhookid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    assignedat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    devicetypevarianttbl: Mapped['Devicetypevarianttbl'] = relationship('Devicetypevarianttbl', back_populates='webhooksperdevicetypetbl')


class Webhookstbl(Base):
    __tablename__ = 'webhookstbl'
    __table_args__ = (
        ForeignKeyConstraint(['accountid'], ['accountstbl.accountid'], name='fk_accountstbl_id'),
        PrimaryKeyConstraint('webhookid', name='webhookstbl_pkey')
    )

    webhookid: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(String(256), nullable=False)
    scheme: Mapped[str] = mapped_column(String(10), nullable=False)
    authprotocol: Mapped[int] = mapped_column(Integer, nullable=False)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    isactive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    authorizationheader: Mapped[Optional[str]] = mapped_column(String(256))
    authrequesturl: Mapped[Optional[str]] = mapped_column(String(256))
    authrequestscheme: Mapped[Optional[str]] = mapped_column(String(10))
    authrequestcontenttype: Mapped[Optional[str]] = mapped_column(String(32))
    authrequestbody: Mapped[Optional[str]] = mapped_column(String(128))
    authrsptokentypefield: Mapped[Optional[str]] = mapped_column(String(128))
    authrsptokenfield: Mapped[Optional[str]] = mapped_column(String(128))
    authrspexpiresinfield: Mapped[Optional[str]] = mapped_column(String(128))
    header0name: Mapped[Optional[str]] = mapped_column(String(32))
    header0value: Mapped[Optional[str]] = mapped_column(String(256))
    header1name: Mapped[Optional[str]] = mapped_column(String(32))
    header1value: Mapped[Optional[str]] = mapped_column(String(256))

    accountstbl: Mapped['Accountstbl'] = relationship('Accountstbl', back_populates='webhookstbl')


class Binaryimageuploadstbl(Base):
    __tablename__ = 'binaryimageuploadstbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', 'binaryclassname', 'timestamp', name='binaryimageuploadstbl_pkey'),
        Index('idx_binaryimageuploadstbl_deviceid', 'deviceid'),
        Index('idx_binaryimageuploadstbl_timecreated', 'timecompleted')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    binaryclassname: Mapped[str] = mapped_column(String(255), primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)
    totallength: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timecompleted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    devicestbl: Mapped['Devicestbl'] = relationship('Devicestbl', back_populates='binaryimageuploadstbl')


class Configbeacontbl(Devicestbl):
    __tablename__ = 'configbeacontbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='configbeacontbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    isenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    isbeacon: Mapped[bool] = mapped_column(Boolean, nullable=False)
    beaconper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    beacondur: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    beaconpwr: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sessionkeycrc: Mapped[int] = mapped_column(Integer, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configbiometrictbl(Devicestbl):
    __tablename__ = 'configbiometrictbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='configbiometrictbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    forcecheckin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lowriskstatereportperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    increasedriskhsithreshold: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    increasedriskstatereportperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    emergencyhsithreshold: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    emergencystatereportperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


t_configdronemodetbl = Table(
    'configdronemodetbl', Base.metadata,
    Column('deviceid', BigInteger, nullable=False),
    Column('ondronepositionperiod', Integer, nullable=False),
    Column('dronecheckperiod', Integer, nullable=False),
    Column('hifreqpsdbin', Integer, nullable=False),
    Column('hifreqondronepercentage', Integer, nullable=False),
    Column('psdsumthreshold', Integer, nullable=False),
    Column('uploadpsd', Boolean, nullable=False),
    Column('accelerometersamplerate', Integer, nullable=False),
    Column('numaxes', Integer, nullable=False),
    Column('nenter', Integer, nullable=False),
    Column('nexit', Integer, nullable=False),
    Column('timeenacted', DateTime, nullable=False),
    Column('lastsent', DateTime),
    Column('lastconfirmed', DateTime),
    Column('buttonpressforcedronemode', Boolean, nullable=False, server_default=text('false')),
    ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id')
)


class Configemergencyv2tbl(Devicestbl):
    __tablename__ = 'configemergencyv2tbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='configemergencyv2tbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timelimit: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    btnactivationtime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    btntimeout: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configfalltbl(Devicestbl):
    __tablename__ = 'configfalltbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='configfalltbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    isjumpmodeenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    jumpstategpsper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    jumpstatedur: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    xlrfreefallthresh: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    xlrfreefalldur: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    altchangefreefalltrigger: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    altchangejumptrigger: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stablealtnumsamples: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stablealtthresh: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configgpstbl(Devicestbl):
    __tablename__ = 'configgpstbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='configgpstbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ispsmenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    aidingenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gnssupdatefreq: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    targetfixaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    targetfixpdop: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configgroundtbl(Devicestbl):
    __tablename__ = 'configgroundtbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='configgroundtbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    gpshbper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    contmotionper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stopmotiontimeout: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hbacqtimeout: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motionacqtimeout: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motionthresh: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motiondur: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    startmotionwinstart: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    startmotionwinend: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motionacquisitionontime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motioninitialacquisitionontime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Confighipstbl(Devicestbl):
    __tablename__ = 'confighipstbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='confighipstbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mode: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    scanconstantly: Mapped[bool] = mapped_column(Boolean, nullable=False)
    forcecheckin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reportper: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    groupcode: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sourceuserid: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configloratbl(Devicestbl):
    __tablename__ = 'configloratbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='configloratbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    isloraenabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sessioncrc: Mapped[int] = mapped_column(Integer, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configmodemtbl(Devicestbl):
    __tablename__ = 'configmodemtbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='configmodemtbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shortbackofftime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    normalbackofftime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    longbackofftime: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    registrationtimeoutperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    socketconnectiontimeoutperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    connectionfailurethreshold: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sockettimeoutperiod: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    flags: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    defaulttosim1: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    preventsimswap: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Devicefirmwarecurrenttbl(Base):
    __tablename__ = 'devicefirmwarecurrenttbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', 'appid', name='devicefirmwarecurrenttbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    majorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    minorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    releasetrack: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ismfg: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lastupdated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    devicestbl: Mapped['Devicestbl'] = relationship('Devicestbl', back_populates='devicefirmwarecurrenttbl')


class Devicestatustbl(Devicestbl):
    __tablename__ = 'devicestatustbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('deviceid', name='devicestatustbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lastboottime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("'1970-01-01 00:00:00'::timestamp without time zone"))
    lastpostime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("'1970-01-01 00:00:00'::timestamp without time zone"))
    lastcommfailtime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("'1970-01-01 00:00:00'::timestamp without time zone"))
    lastappfailtime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("'1970-01-01 00:00:00'::timestamp without time zone"))
    latitude: Mapped[float] = mapped_column(Double(53), nullable=False, server_default=text('0'))
    longitude: Mapped[float] = mapped_column(Double(53), nullable=False, server_default=text('0'))
    gpsaltitude: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    horizontalaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    verticalaccuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    battpercent: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    battvoltage: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    updatereason: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    bootreason: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    hascommhwfail: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    hasapphwfail: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    emereventid: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    posrecordid: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text('0'))
    commhwfailrecordid: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text('0'))
    apphwfailrecordid: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text('0'))
    bootrecordid: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text('0'))


class Devicetransferstbl(Devicestbl):
    __tablename__ = 'devicetransferstbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        ForeignKeyConstraint(['targetid'], ['devicetransfertargetstbl.targetid'], name='fk_devicetransfertargets'),
        PrimaryKeyConstraint('deviceid', name='devicetransferstbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    targetid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    isacked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timesenttodevice: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    timereturnedtoserver: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    devicetransfertargetstbl: Mapped['Devicetransfertargetstbl'] = relationship('Devicetransfertargetstbl', back_populates='devicetransferstbl')


class Fuotaplanstagestbl(Base):
    __tablename__ = 'fuotaplanstagestbl'
    __table_args__ = (
        ForeignKeyConstraint(['planid'], ['fuotaplanstbl.planid'], name='fk_planid'),
        PrimaryKeyConstraint('planid', 'updatestage', name='fuotaplanstagestbl_pkey')
    )

    planid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    updatestage: Mapped[int] = mapped_column(Integer, primary_key=True)
    stagedesc: Mapped[str] = mapped_column(String(256), nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    skippable: Mapped[bool] = mapped_column(Boolean, nullable=False)

    fuotaplanstbl: Mapped['Fuotaplanstbl'] = relationship('Fuotaplanstbl', back_populates='fuotaplanstagestbl')


class Fuotaplanstagetargetstbl(Base):
    __tablename__ = 'fuotaplanstagetargetstbl'
    __table_args__ = (
        ForeignKeyConstraint(['planid'], ['fuotaplanstbl.planid'], name='fk_planid'),
        PrimaryKeyConstraint('planid', 'updatestage', 'appid', name='fuotaplanstagetargetstbl_pkey')
    )

    planid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    updatestage: Mapped[int] = mapped_column(Integer, primary_key=True)
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    releasetrack: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ismfg: Mapped[bool] = mapped_column(Boolean, nullable=False)
    majorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    minorversion: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updateorder: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))

    fuotaplanstbl: Mapped['Fuotaplanstbl'] = relationship('Fuotaplanstbl', back_populates='fuotaplanstagetargetstbl')


class Fuotasettingsperdevicetbl(Devicestbl):
    __tablename__ = 'fuotasettingsperdevicetbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        ForeignKeyConstraint(['planid'], ['fuotaplanstbl.planid'], name='fk_planid'),
        PrimaryKeyConstraint('deviceid', name='fuotasettingsperdevicetbl_pkey')
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    enablefuota: Mapped[bool] = mapped_column(Boolean, nullable=False)
    maxstage: Mapped[int] = mapped_column(Integer, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    fuotaplanstbl: Mapped['Fuotaplanstbl'] = relationship('Fuotaplanstbl', back_populates='fuotasettingsperdevicetbl')


class Fuotasettingsperdevicetypetbl(Base):
    __tablename__ = 'fuotasettingsperdevicetypetbl'
    __table_args__ = (
        ForeignKeyConstraint(['devicetypeid', 'devicevariantid'], ['devicetypevarianttbl.devicetypeid', 'devicetypevarianttbl.devicevariantid'], name='fk_devicetype'),
        ForeignKeyConstraint(['planid'], ['fuotaplanstbl.planid'], name='fk_planid'),
        PrimaryKeyConstraint('devicetypeid', 'devicevariantid', 'accountid', name='fuotasettingsperdevicetypetbl_pkey')
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    accountid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    enablefuota: Mapped[bool] = mapped_column(Boolean, nullable=False)
    maxstage: Mapped[int] = mapped_column(Integer, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    devicetypevarianttbl: Mapped['Devicetypevarianttbl'] = relationship('Devicetypevarianttbl', back_populates='fuotasettingsperdevicetypetbl')
    fuotaplanstbl: Mapped['Fuotaplanstbl'] = relationship('Fuotaplanstbl', back_populates='fuotasettingsperdevicetypetbl')


class Loginpermissiongrantshistorytbl(Base):
    __tablename__ = 'loginpermissiongrantshistorytbl'
    __table_args__ = (
        ForeignKeyConstraint(['loginid'], ['loginstbl.loginid'], name='fk_loginstbl_id'),
        ForeignKeyConstraint(['permissionid'], ['permissionstbl.permissionid'], name='fk_permissionstbl_id'),
        PrimaryKeyConstraint('recordid', name='loginpermissiongrantshistorytbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    loginid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    permissionid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timegranted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timerevoked: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    loginstbl: Mapped['Loginstbl'] = relationship('Loginstbl', back_populates='loginpermissiongrantshistorytbl')
    permissionstbl: Mapped['Permissionstbl'] = relationship('Permissionstbl', back_populates='loginpermissiongrantshistorytbl')


class Loginpermissiongrantstbl(Base):
    __tablename__ = 'loginpermissiongrantstbl'
    __table_args__ = (
        ForeignKeyConstraint(['loginid'], ['loginstbl.loginid'], name='fk_loginstbl_id'),
        ForeignKeyConstraint(['permissionid'], ['permissionstbl.permissionid'], name='fk_permissionstbl_id'),
        PrimaryKeyConstraint('loginid', 'permissionid', name='loginpermissiongrantstbl_pkey')
    )

    loginid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    permissionid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timegranted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    loginstbl: Mapped['Loginstbl'] = relationship('Loginstbl', back_populates='loginpermissiongrantstbl')
    permissionstbl: Mapped['Permissionstbl'] = relationship('Permissionstbl', back_populates='loginpermissiongrantstbl')


class Loginrolegrantshistorytbl(Base):
    __tablename__ = 'loginrolegrantshistorytbl'
    __table_args__ = (
        ForeignKeyConstraint(['loginid'], ['loginstbl.loginid'], name='fk_loginstbl_id'),
        ForeignKeyConstraint(['roleid'], ['rolestbl.roleid'], name='fk_rolestbl_id'),
        PrimaryKeyConstraint('recordid', name='loginrolegrantshistorytbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    loginid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    roleid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timegranted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timerevoked: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    loginstbl: Mapped['Loginstbl'] = relationship('Loginstbl', back_populates='loginrolegrantshistorytbl')
    rolestbl: Mapped['Rolestbl'] = relationship('Rolestbl', back_populates='loginrolegrantshistorytbl')


class Loginrolegrantstbl(Base):
    __tablename__ = 'loginrolegrantstbl'
    __table_args__ = (
        ForeignKeyConstraint(['loginid'], ['loginstbl.loginid'], name='fk_loginstbl_id'),
        ForeignKeyConstraint(['roleid'], ['rolestbl.roleid'], name='fk_rolestbl_id'),
        PrimaryKeyConstraint('loginid', 'roleid', name='loginrolegrantstbl_pkey')
    )

    loginid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    roleid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timegranted: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    loginstbl: Mapped['Loginstbl'] = relationship('Loginstbl', back_populates='loginrolegrantstbl')
    rolestbl: Mapped['Rolestbl'] = relationship('Rolestbl', back_populates='loginrolegrantstbl')


class Loginshistorytbl(Loginstbl):
    __tablename__ = 'loginshistorytbl'
    __table_args__ = (
        ForeignKeyConstraint(['loginid'], ['loginstbl.loginid'], name='fk_loginstbl_id'),
        PrimaryKeyConstraint('loginid', name='loginshistorytbl_pkey')
    )

    recordid: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), nullable=False)
    loginid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    accountid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    isactive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    isprivileged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str] = mapped_column(String(64), nullable=False)


class Socketserversessionstbl(Base):
    __tablename__ = 'socketserversessionstbl'
    __table_args__ = (
        ForeignKeyConstraint(['deviceid'], ['devicestbl.deviceid'], name='fk_devicestbl_id'),
        PrimaryKeyConstraint('sessionid', name='socketserversessionstbl_pkey'),
        UniqueConstraint('deviceid', name='socketserversessionstbl_deviceid_key')
    )

    sessionid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lastpacketid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    aeskeycipher: Mapped[str] = mapped_column(String(64), nullable=False)
    mackeycipher: Mapped[str] = mapped_column(String(64), nullable=False)

    devicestbl: Mapped['Devicestbl'] = relationship('Devicestbl', back_populates='socketserversessionstbl')

from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Double,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime


class Base(DeclarativeBase):
    pass


class Accountshistorytbl(Base):
    __tablename__ = "accountshistorytbl"
    __table_args__ = (PrimaryKeyConstraint("recordid", name="accountshistorytbl_pkey"),)

    recordid: Mapped[int] = mapped_column(
        BigInteger,
        Identity(
            start=1,
            increment=1,
            minvalue=1,
            maxvalue=9223372036854775807,
            cycle=False,
            cache=1,
        ),
        primary_key=True,
    )
    accountid: Mapped[int] = mapped_column(BigInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    isactive: Mapped[bool] = mapped_column(Boolean)
    notes: Mapped[str] = mapped_column(String(64))


class Accountstbl(Base):
    __tablename__ = "accountstbl"
    __table_args__ = (PrimaryKeyConstraint("accountid", name="accountstbl_pkey"),)

    accountid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime)
    isactive: Mapped[bool] = mapped_column(Boolean)

    apikeystbl: Mapped[List["Apikeystbl"]] = relationship(
        "Apikeystbl", back_populates="accountstbl"
    )
    devicestbl: Mapped[List["Devicestbl"]] = relationship(
        "Devicestbl", back_populates="accountstbl"
    )
    loginstbl: Mapped[List["Loginstbl"]] = relationship(
        "Loginstbl", back_populates="accountstbl"
    )
    webhookstbl: Mapped[List["Webhookstbl"]] = relationship(
        "Webhookstbl", back_populates="accountstbl"
    )


class Configbeaconhistorytbl(Base):
    __tablename__ = "configbeaconhistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="configbeaconhistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    isenabled: Mapped[bool] = mapped_column(Boolean)
    isbeacon: Mapped[bool] = mapped_column(Boolean)
    beaconper: Mapped[int] = mapped_column(SmallInteger)
    beacondur: Mapped[int] = mapped_column(SmallInteger)
    beaconpwr: Mapped[int] = mapped_column(SmallInteger)
    sessionkeycrc: Mapped[int] = mapped_column(Integer)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configemergencyv2historytbl(Base):
    __tablename__ = "configemergencyv2historytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="configemergencyv2historytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    timelimit: Mapped[int] = mapped_column(SmallInteger)
    btnactivationtime: Mapped[int] = mapped_column(SmallInteger)
    btntimeout: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configfallhistorytbl(Base):
    __tablename__ = "configfallhistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="configfallhistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    isjumpmodeenabled: Mapped[bool] = mapped_column(Boolean)
    jumpstategpsper: Mapped[int] = mapped_column(SmallInteger)
    jumpstatedur: Mapped[int] = mapped_column(SmallInteger)
    xlrfreefallthresh: Mapped[int] = mapped_column(SmallInteger)
    xlrfreefalldur: Mapped[int] = mapped_column(SmallInteger)
    altchangefreefalltrigger: Mapped[int] = mapped_column(SmallInteger)
    altchangejumptrigger: Mapped[int] = mapped_column(SmallInteger)
    stablealtnumsamples: Mapped[int] = mapped_column(SmallInteger)
    stablealtthresh: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configgpshistorytbl(Base):
    __tablename__ = "configgpshistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="configgpshistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    ispsmenabled: Mapped[bool] = mapped_column(Boolean)
    aidingenabled: Mapped[bool] = mapped_column(Boolean)
    gnssupdatefreq: Mapped[int] = mapped_column(SmallInteger)
    targetfixaccuracy: Mapped[int] = mapped_column(SmallInteger)
    targetfixpdop: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configgroundhistorytbl(Base):
    __tablename__ = "configgroundhistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="configgroundhistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    gpshbper: Mapped[int] = mapped_column(SmallInteger)
    contmotionper: Mapped[int] = mapped_column(SmallInteger)
    stopmotiontimeout: Mapped[int] = mapped_column(SmallInteger)
    hbacqtimeout: Mapped[int] = mapped_column(SmallInteger)
    motionacqtimeout: Mapped[int] = mapped_column(SmallInteger)
    motionthresh: Mapped[int] = mapped_column(SmallInteger)
    motiondur: Mapped[int] = mapped_column(SmallInteger)
    startmotionwinstart: Mapped[int] = mapped_column(SmallInteger)
    startmotionwinend: Mapped[int] = mapped_column(SmallInteger)
    motionacquisitionontime: Mapped[int] = mapped_column(SmallInteger)
    motioninitialacquisitionontime: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Confighipshistorytbl(Base):
    __tablename__ = "confighipshistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="confighipshistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    mode: Mapped[int] = mapped_column(SmallInteger)
    scanconstantly: Mapped[bool] = mapped_column(Boolean)
    forcecheckin: Mapped[bool] = mapped_column(Boolean)
    reportper: Mapped[int] = mapped_column(SmallInteger)
    groupcode: Mapped[int] = mapped_column(SmallInteger)
    sourceuserid: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configlorahistorytbl(Base):
    __tablename__ = "configlorahistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="configlorahistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    isloraenabled: Mapped[bool] = mapped_column(Boolean)
    sessioncrc: Mapped[int] = mapped_column(Integer)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configmodemhistorytbl(Base):
    __tablename__ = "configmodemhistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="configmodemhistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    shortbackofftime: Mapped[int] = mapped_column(SmallInteger)
    normalbackofftime: Mapped[int] = mapped_column(SmallInteger)
    longbackofftime: Mapped[int] = mapped_column(SmallInteger)
    registrationtimeoutperiod: Mapped[int] = mapped_column(SmallInteger)
    socketconnectiontimeoutperiod: Mapped[int] = mapped_column(SmallInteger)
    connectionfailurethreshold: Mapped[int] = mapped_column(SmallInteger)
    sockettimeoutperiod: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Deviceaccounthistorytbl(Base):
    __tablename__ = "deviceaccounthistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="deviceaccounthistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(
        BigInteger,
        Identity(
            start=1,
            increment=1,
            minvalue=1,
            maxvalue=9223372036854775807,
            cycle=False,
            cache=1,
        ),
        primary_key=True,
    )
    deviceid: Mapped[int] = mapped_column(BigInteger)
    accountid: Mapped[int] = mapped_column(BigInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)


class Devicefirmwarehistorytbl(Base):
    __tablename__ = "devicefirmwarehistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="devicefirmwarehistorytbl_pkey"),
        Index("idx_devicefirmwarehistorytbl_deviceid", "deviceid"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    appid: Mapped[int] = mapped_column(Integer)
    majorversion: Mapped[int] = mapped_column(Integer)
    minorversion: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    releasetrack: Mapped[int] = mapped_column(SmallInteger)
    ismfg: Mapped[bool] = mapped_column(Boolean)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)


class Devicemessagestbl(Base):
    __tablename__ = "devicemessagestbl"
    __table_args__ = (PrimaryKeyConstraint("recordid", name="devicemessagestbl_pkey"),)

    recordid: Mapped[int] = mapped_column(
        BigInteger,
        Identity(
            start=1,
            increment=1,
            minvalue=1,
            maxvalue=9223372036854775807,
            cycle=False,
            cache=1,
        ),
        primary_key=True,
    )
    isuplink: Mapped[bool] = mapped_column(Boolean)
    interfacetype: Mapped[int] = mapped_column(Integer)
    timeofrecord: Mapped[datetime.datetime] = mapped_column(DateTime)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    accountid: Mapped[int] = mapped_column(BigInteger)
    messageid: Mapped[int] = mapped_column(Integer)
    messageuid: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    devicedatausagetbl: Mapped[List["Devicedatausagetbl"]] = relationship(
        "Devicedatausagetbl",
        foreign_keys="[Devicedatausagetbl.firstrecordid]",
        back_populates="devicemessagestbl",
    )
    devicedatausagetbl_: Mapped[List["Devicedatausagetbl"]] = relationship(
        "Devicedatausagetbl",
        foreign_keys="[Devicedatausagetbl.lastrecordid]",
        back_populates="devicemessagestbl_",
    )


class Deviceprofilestbl(Base):
    __tablename__ = "deviceprofilestbl"
    __table_args__ = (PrimaryKeyConstraint("deviceid", name="deviceprofilestbl_pkey"),)

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    publickeycipher: Mapped[str] = mapped_column(String(256))
    publickeytype: Mapped[int] = mapped_column(Integer)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime)


class Devicetransferhistorytbl(Base):
    __tablename__ = "devicetransferhistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="devicetransferhistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    targetid: Mapped[int] = mapped_column(BigInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    isacked: Mapped[bool] = mapped_column(Boolean)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    timesenttodevice: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    timereturnedtoserver: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Devicetransfertargetstbl(Base):
    __tablename__ = "devicetransfertargetstbl"
    __table_args__ = (
        PrimaryKeyConstraint("targetid", name="devicetransfertargetstbl_pkey"),
    )

    targetid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    timeserverpublickey: Mapped[str] = mapped_column(String(256))
    serverbaseurl: Mapped[str] = mapped_column(String(256))
    devicerekeypath: Mapped[str] = mapped_column(String(128))
    timeserverport: Mapped[int] = mapped_column(Integer)
    sessiongenerationserverport: Mapped[int] = mapped_column(Integer)
    dataserverport: Mapped[int] = mapped_column(Integer)
    requirednssec: Mapped[bool] = mapped_column(Boolean)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)

    devicetransferstbl: Mapped[List["Devicetransferstbl"]] = relationship(
        "Devicetransferstbl", back_populates="devicetransfertargetstbl"
    )


class Devicetypevarianttbl(Base):
    __tablename__ = "devicetypevarianttbl"
    __table_args__ = (
        PrimaryKeyConstraint(
            "devicetypeid", "devicevariantid", name="devicetypevarianttbl_pkey"
        ),
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicetypename: Mapped[str] = mapped_column(String(128))

    devicefirmwareappidstbl: Mapped[List["Devicefirmwareappidstbl"]] = relationship(
        "Devicefirmwareappidstbl", back_populates="devicetypevarianttbl"
    )
    devicestbl: Mapped[List["Devicestbl"]] = relationship(
        "Devicestbl", back_populates="devicetypevarianttbl"
    )
    fuotaplanstbl: Mapped[List["Fuotaplanstbl"]] = relationship(
        "Fuotaplanstbl", back_populates="devicetypevarianttbl"
    )
    webhooksperdevicetypetbl: Mapped[List["Webhooksperdevicetypetbl"]] = relationship(
        "Webhooksperdevicetypetbl", back_populates="devicetypevarianttbl"
    )
    fuotasettingsperdevicetypetbl: Mapped[List["Fuotasettingsperdevicetypetbl"]] = (
        relationship(
            "Fuotasettingsperdevicetypetbl", back_populates="devicetypevarianttbl"
        )
    )


class Fuotaprogresshistorytbl(Base):
    __tablename__ = "fuotaprogresshistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="fuotaprogresshistorytbl_pkey"),
        Index("idx_fuotaprogresshistorytbl_deviceid", "deviceid"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    appid: Mapped[int] = mapped_column(Integer)
    majorversion: Mapped[int] = mapped_column(Integer)
    minorversion: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    releasetrack: Mapped[int] = mapped_column(SmallInteger)
    ismfg: Mapped[bool] = mapped_column(Boolean)
    pagesapplied: Mapped[int] = mapped_column(Integer)
    totalpages: Mapped[int] = mapped_column(Integer)
    timestarted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timefinished: Mapped[datetime.datetime] = mapped_column(DateTime)


class Fuotaprogresstbl(Base):
    __tablename__ = "fuotaprogresstbl"
    __table_args__ = (
        PrimaryKeyConstraint("deviceid", "appid", name="fuotaprogresstbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    majorversion: Mapped[int] = mapped_column(Integer)
    minorversion: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    releasetrack: Mapped[int] = mapped_column(SmallInteger)
    ismfg: Mapped[bool] = mapped_column(Boolean)
    pagesapplied: Mapped[int] = mapped_column(Integer)
    totalpages: Mapped[int] = mapped_column(Integer)
    timestarted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastupdated: Mapped[datetime.datetime] = mapped_column(DateTime)


class Fuotasettingsperdevicehistorytbl(Base):
    __tablename__ = "fuotasettingsperdevicehistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint("recordid", name="fuotasettingsperdevicehistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    planid: Mapped[int] = mapped_column(BigInteger)
    enablefuota: Mapped[bool] = mapped_column(Boolean)
    maxstage: Mapped[int] = mapped_column(Integer)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)


class Fuotasettingsperdevicetypehistorytbl(Base):
    __tablename__ = "fuotasettingsperdevicetypehistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint(
            "recordid", name="fuotasettingsperdevicetypehistorytbl_pkey"
        ),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    devicetypeid: Mapped[int] = mapped_column(Integer)
    devicevariantid: Mapped[int] = mapped_column(Integer)
    accountid: Mapped[int] = mapped_column(BigInteger)
    planid: Mapped[int] = mapped_column(BigInteger)
    enablefuota: Mapped[bool] = mapped_column(Boolean)
    maxstage: Mapped[int] = mapped_column(Integer)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)


class Permissionstbl(Base):
    __tablename__ = "permissionstbl"
    __table_args__ = (
        PrimaryKeyConstraint("permissionid", name="permissionstbl_pkey"),
        UniqueConstraint("permissionkey", name="permissionstbl_permissionkey_key"),
    )

    permissionid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    permissionkey: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(256))

    rolestbl: Mapped[List["Rolestbl"]] = relationship(
        "Rolestbl", secondary="rolepermissiongrantstbl", back_populates="permissionstbl"
    )
    loginpermissiongrantshistorytbl: Mapped[List["Loginpermissiongrantshistorytbl"]] = (
        relationship("Loginpermissiongrantshistorytbl", back_populates="permissionstbl")
    )
    loginpermissiongrantstbl: Mapped[List["Loginpermissiongrantstbl"]] = relationship(
        "Loginpermissiongrantstbl", back_populates="permissionstbl"
    )


class Rolestbl(Base):
    __tablename__ = "rolestbl"
    __table_args__ = (
        PrimaryKeyConstraint("roleid", name="rolestbl_pkey"),
        UniqueConstraint("rolekey", name="rolestbl_rolekey_key"),
    )

    roleid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rolekey: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(256))

    permissionstbl: Mapped[List["Permissionstbl"]] = relationship(
        "Permissionstbl", secondary="rolepermissiongrantstbl", back_populates="rolestbl"
    )
    rolestbl: Mapped[List["Rolestbl"]] = relationship(
        "Rolestbl",
        secondary="roleinheritancetbl",
        primaryjoin=lambda: Rolestbl.roleid == t_roleinheritancetbl.c.childroleid,
        secondaryjoin=lambda: Rolestbl.roleid == t_roleinheritancetbl.c.parentroleid,
        back_populates="rolestbl_",
    )
    rolestbl_: Mapped[List["Rolestbl"]] = relationship(
        "Rolestbl",
        secondary="roleinheritancetbl",
        primaryjoin=lambda: Rolestbl.roleid == t_roleinheritancetbl.c.parentroleid,
        secondaryjoin=lambda: Rolestbl.roleid == t_roleinheritancetbl.c.childroleid,
        back_populates="rolestbl",
    )
    loginrolegrantshistorytbl: Mapped[List["Loginrolegrantshistorytbl"]] = relationship(
        "Loginrolegrantshistorytbl", back_populates="rolestbl"
    )
    loginrolegrantstbl: Mapped[List["Loginrolegrantstbl"]] = relationship(
        "Loginrolegrantstbl", back_populates="rolestbl"
    )


class Schemaversions(Base):
    __tablename__ = "schemaversions"
    __table_args__ = (
        PrimaryKeyConstraint("schemaversionsid", name="PK_schemaversions_Id"),
    )

    schemaversionsid: Mapped[int] = mapped_column(Integer, primary_key=True)
    scriptname: Mapped[str] = mapped_column(String(255))
    applied: Mapped[datetime.datetime] = mapped_column(DateTime)


class Webhooksperdevicehistorytbl(Base):
    __tablename__ = "webhooksperdevicehistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint(
            "deviceid",
            "webhookid",
            "unassignedat",
            name="webhooksperdevicehistorytbl_pkey",
        ),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    webhookid: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignedat: Mapped[datetime.datetime] = mapped_column(DateTime)
    unassignedat: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)


class Webhooksperdevicetbl(Base):
    __tablename__ = "webhooksperdevicetbl"
    __table_args__ = (
        PrimaryKeyConstraint("deviceid", "webhookid", name="webhooksperdevicetbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    webhookid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    assignedat: Mapped[datetime.datetime] = mapped_column(DateTime)


class Webhooksperdevicetypehistorytbl(Base):
    __tablename__ = "webhooksperdevicetypehistorytbl"
    __table_args__ = (
        PrimaryKeyConstraint(
            "devicetypeid",
            "devicevariantid",
            "unassignedat",
            name="webhooksperdevicetypehistorytbl_pkey",
        ),
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhookid: Mapped[int] = mapped_column(BigInteger)
    assignedat: Mapped[datetime.datetime] = mapped_column(DateTime)
    unassignedat: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)


class Apikeystbl(Base):
    __tablename__ = "apikeystbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["accountid"], ["accountstbl.accountid"], name="fk_accountstbl_id"
        ),
        PrimaryKeyConstraint("id", name="apikeystbl_pkey"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(
            start=1,
            increment=1,
            minvalue=1,
            maxvalue=9223372036854775807,
            cycle=False,
            cache=1,
        ),
        primary_key=True,
    )
    description: Mapped[str] = mapped_column(String(128))
    key: Mapped[str] = mapped_column(String(256))
    accountid: Mapped[int] = mapped_column(BigInteger)
    isactive: Mapped[bool] = mapped_column(Boolean)
    datetimeissued: Mapped[datetime.datetime] = mapped_column(DateTime)
    datetimerevoked: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    revocationreason: Mapped[Optional[str]] = mapped_column(String(128))

    accountstbl: Mapped["Accountstbl"] = relationship(
        "Accountstbl", back_populates="apikeystbl"
    )


class Devicedatausagetbl(Base):
    __tablename__ = "devicedatausagetbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["firstrecordid"],
            ["devicemessagestbl.recordid"],
            name="fk_devicemessagestbl_first_id",
        ),
        ForeignKeyConstraint(
            ["lastrecordid"],
            ["devicemessagestbl.recordid"],
            name="fk_devicemessagestbl_last_id",
        ),
        PrimaryKeyConstraint("dayid", "deviceid", name="devicedatausagetbl_pkey"),
    )

    dayid: Mapped[int] = mapped_column(Integer, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    interfacetype: Mapped[int] = mapped_column(Integer)
    bytesreceived: Mapped[int] = mapped_column(Integer)
    bytessent: Mapped[int] = mapped_column(Integer)
    firstrecordid: Mapped[int] = mapped_column(BigInteger)
    lastrecordid: Mapped[int] = mapped_column(BigInteger)

    devicemessagestbl: Mapped["Devicemessagestbl"] = relationship(
        "Devicemessagestbl",
        foreign_keys=[firstrecordid],
        back_populates="devicedatausagetbl",
    )
    devicemessagestbl_: Mapped["Devicemessagestbl"] = relationship(
        "Devicemessagestbl",
        foreign_keys=[lastrecordid],
        back_populates="devicedatausagetbl_",
    )


class Devicefirmwareappidstbl(Base):
    __tablename__ = "devicefirmwareappidstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["devicetypeid", "devicevariantid"],
            [
                "devicetypevarianttbl.devicetypeid",
                "devicetypevarianttbl.devicevariantid",
            ],
            name="fk_devicetype",
        ),
        PrimaryKeyConstraint(
            "devicetypeid",
            "devicevariantid",
            "appid",
            name="devicefirmwareappidstbl_pkey",
        ),
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    isauxiliary: Mapped[bool] = mapped_column(Boolean)

    devicetypevarianttbl: Mapped["Devicetypevarianttbl"] = relationship(
        "Devicetypevarianttbl", back_populates="devicefirmwareappidstbl"
    )


class Devicestbl(Base):
    __tablename__ = "devicestbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["accountid"], ["accountstbl.accountid"], name="fk_accountstbl_id"
        ),
        ForeignKeyConstraint(
            ["devicetypeid", "devvariantid"],
            [
                "devicetypevarianttbl.devicetypeid",
                "devicetypevarianttbl.devicevariantid",
            ],
            name="fk_devicetype",
        ),
        PrimaryKeyConstraint("deviceid", name="devicestbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    devicetypeid: Mapped[int] = mapped_column(Integer)
    devvariantid: Mapped[int] = mapped_column(Integer)
    accountid: Mapped[int] = mapped_column(BigInteger)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime)
    isactive: Mapped[bool] = mapped_column(Boolean)

    accountstbl: Mapped["Accountstbl"] = relationship(
        "Accountstbl", back_populates="devicestbl"
    )
    devicetypevarianttbl: Mapped["Devicetypevarianttbl"] = relationship(
        "Devicetypevarianttbl", back_populates="devicestbl"
    )
    devicefirmwarecurrenttbl: Mapped[List["Devicefirmwarecurrenttbl"]] = relationship(
        "Devicefirmwarecurrenttbl", back_populates="devicestbl"
    )
    socketserversessionstbl: Mapped["Socketserversessionstbl"] = relationship(
        "Socketserversessionstbl", uselist=False, back_populates="devicestbl"
    )


class Fuotaplanstbl(Base):
    __tablename__ = "fuotaplanstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["devicetypeid", "devicevariantid"],
            [
                "devicetypevarianttbl.devicetypeid",
                "devicetypevarianttbl.devicevariantid",
            ],
            name="fk_devicetype",
        ),
        PrimaryKeyConstraint("planid", name="fuotaplanstbl_pkey"),
    )

    planid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plandesc: Mapped[str] = mapped_column(String(256))
    devicetypeid: Mapped[int] = mapped_column(Integer)
    devicevariantid: Mapped[int] = mapped_column(Integer)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime)

    devicetypevarianttbl: Mapped["Devicetypevarianttbl"] = relationship(
        "Devicetypevarianttbl", back_populates="fuotaplanstbl"
    )
    fuotaplanstagestbl: Mapped[List["Fuotaplanstagestbl"]] = relationship(
        "Fuotaplanstagestbl", back_populates="fuotaplanstbl"
    )
    fuotaplanstagetargetstbl: Mapped[List["Fuotaplanstagetargetstbl"]] = relationship(
        "Fuotaplanstagetargetstbl", back_populates="fuotaplanstbl"
    )
    fuotasettingsperdevicetbl: Mapped[List["Fuotasettingsperdevicetbl"]] = relationship(
        "Fuotasettingsperdevicetbl", back_populates="fuotaplanstbl"
    )
    fuotasettingsperdevicetypetbl: Mapped[List["Fuotasettingsperdevicetypetbl"]] = (
        relationship("Fuotasettingsperdevicetypetbl", back_populates="fuotaplanstbl")
    )


class Loginstbl(Base):
    __tablename__ = "loginstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["accountid"], ["accountstbl.accountid"], name="fk_accountstbl_id"
        ),
        PrimaryKeyConstraint("loginid", name="loginstbl_pkey"),
    )

    loginid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    accountid: Mapped[int] = mapped_column(BigInteger)
    isactive: Mapped[bool] = mapped_column(Boolean)
    isprivileged: Mapped[bool] = mapped_column(Boolean)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime)

    accountstbl: Mapped["Accountstbl"] = relationship(
        "Accountstbl", back_populates="loginstbl"
    )
    loginpermissiongrantshistorytbl: Mapped[List["Loginpermissiongrantshistorytbl"]] = (
        relationship("Loginpermissiongrantshistorytbl", back_populates="loginstbl")
    )
    loginpermissiongrantstbl: Mapped[List["Loginpermissiongrantstbl"]] = relationship(
        "Loginpermissiongrantstbl", back_populates="loginstbl"
    )
    loginrolegrantshistorytbl: Mapped[List["Loginrolegrantshistorytbl"]] = relationship(
        "Loginrolegrantshistorytbl", back_populates="loginstbl"
    )
    loginrolegrantstbl: Mapped[List["Loginrolegrantstbl"]] = relationship(
        "Loginrolegrantstbl", back_populates="loginstbl"
    )


class Messagesalphahwfailtbl(Devicemessagestbl):
    __tablename__ = "messagesalphahwfailtbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesalphahwfailtbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime)
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
    __tablename__ = "messagesbeaconpositiontbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesbeaconpositiontbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flags: Mapped[int] = mapped_column(Integer)
    isinmotion: Mapped[bool] = mapped_column(Boolean)
    gnssfixvalid: Mapped[bool] = mapped_column(Boolean)
    gnssfixok: Mapped[bool] = mapped_column(Boolean)
    validdate: Mapped[bool] = mapped_column(Boolean)
    validtime: Mapped[bool] = mapped_column(Boolean)
    confdate: Mapped[bool] = mapped_column(Boolean)
    conftime: Mapped[bool] = mapped_column(Boolean)
    conftimeavail: Mapped[bool] = mapped_column(Boolean)
    oncharger: Mapped[bool] = mapped_column(Boolean)
    usedaiding: Mapped[bool] = mapped_column(Boolean)
    updatereason: Mapped[int] = mapped_column(SmallInteger)
    psmstate: Mapped[int] = mapped_column(SmallInteger)
    numsat: Mapped[int] = mapped_column(SmallInteger)
    fixtype: Mapped[int] = mapped_column(SmallInteger)
    latitude: Mapped[float] = mapped_column(Double(53))
    longitude: Mapped[float] = mapped_column(Double(53))
    horizontalaccuracy: Mapped[int] = mapped_column(SmallInteger)
    gpsaltitude: Mapped[int] = mapped_column(SmallInteger)
    pressurealtitude: Mapped[int] = mapped_column(Integer)
    timeoffix: Mapped[datetime.datetime] = mapped_column(DateTime)
    groundspeed: Mapped[int] = mapped_column(SmallInteger)
    heading: Mapped[int] = mapped_column(SmallInteger)
    airpressure: Mapped[float] = mapped_column(Double(53))
    pdop: Mapped[int] = mapped_column(SmallInteger)
    vertaccuracy: Mapped[int] = mapped_column(SmallInteger)
    beaconid: Mapped[int] = mapped_column(BigInteger)
    rssi: Mapped[int] = mapped_column(SmallInteger)


class Messagesbiometricdatatbl(Devicemessagestbl):
    __tablename__ = "messagesbiometricdatatbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesbiometricdatatbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofmeasurement: Mapped[datetime.datetime] = mapped_column(DateTime)
    flags: Mapped[int] = mapped_column(Integer)
    airpressure: Mapped[int] = mapped_column(SmallInteger)
    externaltemperature: Mapped[float] = mapped_column(Double(53))
    relativehumidity: Mapped[int] = mapped_column(SmallInteger)
    heartrate: Mapped[int] = mapped_column(SmallInteger)
    heartrateconfidence: Mapped[int] = mapped_column(SmallInteger)
    spo2: Mapped[int] = mapped_column(SmallInteger)
    spo2confidence: Mapped[int] = mapped_column(SmallInteger)
    skintemperature: Mapped[float] = mapped_column(Double(53))
    estimatedcoretemperature: Mapped[float] = mapped_column(Double(53))
    heatstrainindex: Mapped[float] = mapped_column(Double(53))
    wobbleindex: Mapped[int] = mapped_column(SmallInteger)
    vsmontime: Mapped[int] = mapped_column(SmallInteger)
    heatemergencyeventid: Mapped[int] = mapped_column(Integer)


class Messagesblesessionkeytbl(Devicemessagestbl):
    __tablename__ = "messagesblesessionkeytbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesblesessionkeytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sessionkeycrc: Mapped[int] = mapped_column(Integer)


class Messagesboottbl(Devicemessagestbl):
    __tablename__ = "messagesboottbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesboottbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofboot: Mapped[datetime.datetime] = mapped_column(DateTime)
    flags: Mapped[int] = mapped_column(Integer)
    chipid: Mapped[int] = mapped_column(SmallInteger)
    bootreason: Mapped[int] = mapped_column(SmallInteger)
    numexceptions: Mapped[int] = mapped_column(SmallInteger)


class Messagescommshwfailtbl(Devicemessagestbl):
    __tablename__ = "messagescommshwfailtbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagescommshwfailtbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime)
    simfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    sx1262fails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    ipcfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    extflashfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    secelemfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    satmodemfails: Mapped[Optional[int]] = mapped_column(SmallInteger)


class Messagesemergencyeventresptbl(Devicemessagestbl):
    __tablename__ = "messagesemergencyeventresptbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesemergencyeventresptbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    emergencyeventid: Mapped[int] = mapped_column(Integer)
    flags: Mapped[int] = mapped_column(SmallInteger)


class Messagesemergencypositiontbl(Devicemessagestbl):
    __tablename__ = "messagesemergencypositiontbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesemergencypositiontbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flags: Mapped[int] = mapped_column(Integer)
    isinmotion: Mapped[bool] = mapped_column(Boolean)
    gnssfixvalid: Mapped[bool] = mapped_column(Boolean)
    gnssfixok: Mapped[bool] = mapped_column(Boolean)
    validdate: Mapped[bool] = mapped_column(Boolean)
    validtime: Mapped[bool] = mapped_column(Boolean)
    confdate: Mapped[bool] = mapped_column(Boolean)
    conftime: Mapped[bool] = mapped_column(Boolean)
    conftimeavail: Mapped[bool] = mapped_column(Boolean)
    oncharger: Mapped[bool] = mapped_column(Boolean)
    usedaiding: Mapped[bool] = mapped_column(Boolean)
    updatereason: Mapped[int] = mapped_column(SmallInteger)
    psmstate: Mapped[int] = mapped_column(SmallInteger)
    numsat: Mapped[int] = mapped_column(SmallInteger)
    fixtype: Mapped[int] = mapped_column(SmallInteger)
    latitude: Mapped[float] = mapped_column(Double(53))
    longitude: Mapped[float] = mapped_column(Double(53))
    gpsontime: Mapped[int] = mapped_column(SmallInteger)
    horizontalaccuracy: Mapped[int] = mapped_column(SmallInteger)
    gpsaltitude: Mapped[int] = mapped_column(SmallInteger)
    pressurealtitude: Mapped[int] = mapped_column(Integer)
    timeoffix: Mapped[datetime.datetime] = mapped_column(DateTime)
    groundspeed: Mapped[int] = mapped_column(SmallInteger)
    heading: Mapped[int] = mapped_column(SmallInteger)
    battpercent: Mapped[int] = mapped_column(SmallInteger)
    airpressure: Mapped[float] = mapped_column(Double(53))
    temperature: Mapped[float] = mapped_column(Double(53))
    pdop: Mapped[int] = mapped_column(SmallInteger)
    vertaccuracy: Mapped[int] = mapped_column(SmallInteger)
    emergencyeventid: Mapped[int] = mapped_column(Integer)


class Messagesfalleventtbl(Devicemessagestbl):
    __tablename__ = "messagesfalleventtbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesfalleventtbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeoffall: Mapped[datetime.datetime] = mapped_column(DateTime)
    flags: Mapped[int] = mapped_column(Integer)


class Messageshipsdatatbl(Devicemessagestbl):
    __tablename__ = "messageshipsdatatbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messageshipsdatatbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofsample: Mapped[datetime.datetime] = mapped_column(DateTime)
    groupcode: Mapped[int] = mapped_column(SmallInteger)
    sourceuserid: Mapped[int] = mapped_column(SmallInteger)
    hsidataval: Mapped[int] = mapped_column(SmallInteger)
    hrdataval: Mapped[int] = mapped_column(SmallInteger)
    estcoretemp: Mapped[int] = mapped_column(SmallInteger)
    skintemp: Mapped[int] = mapped_column(SmallInteger)
    nii: Mapped[int] = mapped_column(SmallInteger)
    risk: Mapped[int] = mapped_column(SmallInteger)
    confidence: Mapped[int] = mapped_column(SmallInteger)
    battery: Mapped[int] = mapped_column(SmallInteger)


class Messageshwfailtbl(Devicemessagestbl):
    __tablename__ = "messageshwfailtbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messageshwfailtbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime)
    xlrfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    altfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    gpsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    sx1262fails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    ipcfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bmsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    extflashfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    secelemfails: Mapped[Optional[int]] = mapped_column(SmallInteger)


class Messagesnetworkstatusv4tbl(Devicemessagestbl):
    __tablename__ = "messagesnetworkstatusv4tbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesnetworkstatusv4tbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofconnection: Mapped[datetime.datetime] = mapped_column(DateTime)
    didlteconn: Mapped[bool] = mapped_column(Boolean)
    didsockconn: Mapped[bool] = mapped_column(Boolean)
    sendsuccess: Mapped[bool] = mapped_column(Boolean)
    usednbiot: Mapped[bool] = mapped_column(Boolean)
    didusesim1: Mapped[bool] = mapped_column(Boolean)
    didsocketdisconnectearly: Mapped[bool] = mapped_column(Boolean)
    didusednssec: Mapped[bool] = mapped_column(Boolean)
    flags: Mapped[int] = mapped_column(Integer)
    timespent: Mapped[int] = mapped_column(SmallInteger)
    rsrq: Mapped[float] = mapped_column(Double(53))
    rsrp: Mapped[float] = mapped_column(Double(53))
    bytessent: Mapped[int] = mapped_column(Integer)
    bytesreceived: Mapped[int] = mapped_column(Integer)
    band: Mapped[int] = mapped_column(SmallInteger)
    energyestimate: Mapped[int] = mapped_column(SmallInteger)
    networkid: Mapped[int] = mapped_column(Integer)


class Messagespositionv5tbl(Devicemessagestbl):
    __tablename__ = "messagespositionv5tbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagespositionv5tbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flags: Mapped[int] = mapped_column(Integer)
    isinmotion: Mapped[bool] = mapped_column(Boolean)
    gnssfixvalid: Mapped[bool] = mapped_column(Boolean)
    gnssfixok: Mapped[bool] = mapped_column(Boolean)
    validdate: Mapped[bool] = mapped_column(Boolean)
    validtime: Mapped[bool] = mapped_column(Boolean)
    confdate: Mapped[bool] = mapped_column(Boolean)
    conftime: Mapped[bool] = mapped_column(Boolean)
    conftimeavail: Mapped[bool] = mapped_column(Boolean)
    oncharger: Mapped[bool] = mapped_column(Boolean)
    usedaiding: Mapped[bool] = mapped_column(Boolean)
    updatereason: Mapped[int] = mapped_column(SmallInteger)
    psmstate: Mapped[int] = mapped_column(SmallInteger)
    numsat: Mapped[int] = mapped_column(SmallInteger)
    fixtype: Mapped[int] = mapped_column(SmallInteger)
    latitude: Mapped[float] = mapped_column(Double(53))
    longitude: Mapped[float] = mapped_column(Double(53))
    gpsontime: Mapped[int] = mapped_column(SmallInteger)
    horizontalaccuracy: Mapped[int] = mapped_column(SmallInteger)
    gpsaltitude: Mapped[int] = mapped_column(SmallInteger)
    pressurealtitude: Mapped[int] = mapped_column(Integer)
    timeoffix: Mapped[datetime.datetime] = mapped_column(DateTime)
    groundspeed: Mapped[int] = mapped_column(SmallInteger)
    heading: Mapped[int] = mapped_column(SmallInteger)
    battvoltage: Mapped[int] = mapped_column(SmallInteger)
    airpressure: Mapped[float] = mapped_column(Double(53))
    temperature: Mapped[float] = mapped_column(Double(53))
    avgforce: Mapped[float] = mapped_column(Double(53))
    maxforce: Mapped[float] = mapped_column(Double(53))
    battpercent: Mapped[int] = mapped_column(SmallInteger)
    pdop: Mapped[int] = mapped_column(SmallInteger)
    bmstemp: Mapped[int] = mapped_column(SmallInteger)
    vertaccuracy: Mapped[int] = mapped_column(SmallInteger)
    emergencyeventid: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class Messagesreboottbl(Devicemessagestbl):
    __tablename__ = "messagesreboottbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesreboottbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commsflags: Mapped[int] = mapped_column(Integer)
    appflags: Mapped[int] = mapped_column(Integer)


class Messagesscratchpadtbl(Devicemessagestbl):
    __tablename__ = "messagesscratchpadtbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagesscratchpadtbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payload: Mapped[Optional[str]] = mapped_column(String(771))


class Messagessigma5hwfailtbl(Devicemessagestbl):
    __tablename__ = "messagessigma5hwfailtbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="messagessigma5hwfailtbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeofevent: Mapped[datetime.datetime] = mapped_column(DateTime)
    xlrfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    altfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    gpsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bmsfails: Mapped[Optional[int]] = mapped_column(SmallInteger)
    extflashfails: Mapped[Optional[int]] = mapped_column(SmallInteger)


t_roleinheritancetbl = Table(
    "roleinheritancetbl",
    Base.metadata,
    Column("parentroleid", BigInteger, primary_key=True, nullable=False),
    Column("childroleid", BigInteger, primary_key=True, nullable=False),
    ForeignKeyConstraint(
        ["childroleid"], ["rolestbl.roleid"], name="fk_rolestbl_id_parent"
    ),
    ForeignKeyConstraint(["parentroleid"], ["rolestbl.roleid"], name="fk_rolestbl_id"),
    PrimaryKeyConstraint("parentroleid", "childroleid", name="roleinheritancetbl_pkey"),
)


t_rolepermissiongrantstbl = Table(
    "rolepermissiongrantstbl",
    Base.metadata,
    Column("roleid", BigInteger, primary_key=True, nullable=False),
    Column("permissionid", BigInteger, primary_key=True, nullable=False),
    ForeignKeyConstraint(
        ["permissionid"], ["permissionstbl.permissionid"], name="fk_permissionstbl_id"
    ),
    ForeignKeyConstraint(["roleid"], ["rolestbl.roleid"], name="fk_rolestbl_id"),
    PrimaryKeyConstraint("roleid", "permissionid", name="rolepermissiongrantstbl_pkey"),
)


class Socketserver1messagestbl(Devicemessagestbl):
    __tablename__ = "socketserver1messagestbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recordid"], ["devicemessagestbl.recordid"], name="fk_devicemessagestbl_id"
        ),
        PrimaryKeyConstraint("recordid", name="socketserver1messagestbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    packetid: Mapped[int] = mapped_column(BigInteger)
    didack: Mapped[bool] = mapped_column(Boolean)
    didnak: Mapped[bool] = mapped_column(Boolean)


class Webhooksperdevicetypetbl(Base):
    __tablename__ = "webhooksperdevicetypetbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["devicetypeid", "devicevariantid"],
            [
                "devicetypevarianttbl.devicetypeid",
                "devicetypevarianttbl.devicevariantid",
            ],
            name="fk_devicetype",
        ),
        PrimaryKeyConstraint(
            "devicetypeid",
            "devicevariantid",
            "webhookid",
            name="webhooksperdevicetypetbl_pkey",
        ),
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhookid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    assignedat: Mapped[datetime.datetime] = mapped_column(DateTime)

    devicetypevarianttbl: Mapped["Devicetypevarianttbl"] = relationship(
        "Devicetypevarianttbl", back_populates="webhooksperdevicetypetbl"
    )


class Webhookstbl(Base):
    __tablename__ = "webhookstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["accountid"], ["accountstbl.accountid"], name="fk_accountstbl_id"
        ),
        PrimaryKeyConstraint("webhookid", name="webhookstbl_pkey"),
    )

    webhookid: Mapped[int] = mapped_column(
        BigInteger,
        Identity(
            start=1,
            increment=1,
            minvalue=1,
            maxvalue=9223372036854775807,
            cycle=False,
            cache=1,
        ),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(256))
    scheme: Mapped[str] = mapped_column(String(10))
    authprotocol: Mapped[int] = mapped_column(Integer)
    accountid: Mapped[int] = mapped_column(BigInteger)
    isactive: Mapped[bool] = mapped_column(Boolean)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime)
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

    accountstbl: Mapped["Accountstbl"] = relationship(
        "Accountstbl", back_populates="webhookstbl"
    )


class Configbeacontbl(Devicestbl):
    __tablename__ = "configbeacontbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="configbeacontbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    isenabled: Mapped[bool] = mapped_column(Boolean)
    isbeacon: Mapped[bool] = mapped_column(Boolean)
    beaconper: Mapped[int] = mapped_column(SmallInteger)
    beacondur: Mapped[int] = mapped_column(SmallInteger)
    beaconpwr: Mapped[int] = mapped_column(SmallInteger)
    sessionkeycrc: Mapped[int] = mapped_column(Integer)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configbiometrictbl(Devicestbl):
    __tablename__ = "configbiometrictbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="configbiometrictbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    forcecheckin: Mapped[bool] = mapped_column(Boolean)
    lowriskstatereportperiod: Mapped[int] = mapped_column(SmallInteger)
    increasedriskhsithreshold: Mapped[int] = mapped_column(SmallInteger)
    increasedriskstatereportperiod: Mapped[int] = mapped_column(SmallInteger)
    emergencyhsithreshold: Mapped[int] = mapped_column(SmallInteger)
    emergencystatereportperiod: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configemergencyv2tbl(Devicestbl):
    __tablename__ = "configemergencyv2tbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="configemergencyv2tbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timelimit: Mapped[int] = mapped_column(SmallInteger)
    btnactivationtime: Mapped[int] = mapped_column(SmallInteger)
    btntimeout: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configfalltbl(Devicestbl):
    __tablename__ = "configfalltbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="configfalltbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    isjumpmodeenabled: Mapped[bool] = mapped_column(Boolean)
    jumpstategpsper: Mapped[int] = mapped_column(SmallInteger)
    jumpstatedur: Mapped[int] = mapped_column(SmallInteger)
    xlrfreefallthresh: Mapped[int] = mapped_column(SmallInteger)
    xlrfreefalldur: Mapped[int] = mapped_column(SmallInteger)
    altchangefreefalltrigger: Mapped[int] = mapped_column(SmallInteger)
    altchangejumptrigger: Mapped[int] = mapped_column(SmallInteger)
    stablealtnumsamples: Mapped[int] = mapped_column(SmallInteger)
    stablealtthresh: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configgpstbl(Devicestbl):
    __tablename__ = "configgpstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="configgpstbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ispsmenabled: Mapped[bool] = mapped_column(Boolean)
    aidingenabled: Mapped[bool] = mapped_column(Boolean)
    gnssupdatefreq: Mapped[int] = mapped_column(SmallInteger)
    targetfixaccuracy: Mapped[int] = mapped_column(SmallInteger)
    targetfixpdop: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configgroundtbl(Devicestbl):
    __tablename__ = "configgroundtbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="configgroundtbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    gpshbper: Mapped[int] = mapped_column(SmallInteger)
    contmotionper: Mapped[int] = mapped_column(SmallInteger)
    stopmotiontimeout: Mapped[int] = mapped_column(SmallInteger)
    hbacqtimeout: Mapped[int] = mapped_column(SmallInteger)
    motionacqtimeout: Mapped[int] = mapped_column(SmallInteger)
    motionthresh: Mapped[int] = mapped_column(SmallInteger)
    motiondur: Mapped[int] = mapped_column(SmallInteger)
    startmotionwinstart: Mapped[int] = mapped_column(SmallInteger)
    startmotionwinend: Mapped[int] = mapped_column(SmallInteger)
    motionacquisitionontime: Mapped[int] = mapped_column(SmallInteger)
    motioninitialacquisitionontime: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Confighipstbl(Devicestbl):
    __tablename__ = "confighipstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="confighipstbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mode: Mapped[int] = mapped_column(SmallInteger)
    scanconstantly: Mapped[bool] = mapped_column(Boolean)
    forcecheckin: Mapped[bool] = mapped_column(Boolean)
    reportper: Mapped[int] = mapped_column(SmallInteger)
    groupcode: Mapped[int] = mapped_column(SmallInteger)
    sourceuserid: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configloratbl(Devicestbl):
    __tablename__ = "configloratbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="configloratbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    isloraenabled: Mapped[bool] = mapped_column(Boolean)
    sessioncrc: Mapped[int] = mapped_column(Integer)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Configmodemtbl(Devicestbl):
    __tablename__ = "configmodemtbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="configmodemtbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shortbackofftime: Mapped[int] = mapped_column(SmallInteger)
    normalbackofftime: Mapped[int] = mapped_column(SmallInteger)
    longbackofftime: Mapped[int] = mapped_column(SmallInteger)
    registrationtimeoutperiod: Mapped[int] = mapped_column(SmallInteger)
    socketconnectiontimeoutperiod: Mapped[int] = mapped_column(SmallInteger)
    connectionfailurethreshold: Mapped[int] = mapped_column(SmallInteger)
    sockettimeoutperiod: Mapped[int] = mapped_column(SmallInteger)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    flags: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    defaulttosim1: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    preventsimswap: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    lastsent: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lastconfirmed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Devicefirmwarecurrenttbl(Base):
    __tablename__ = "devicefirmwarecurrenttbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", "appid", name="devicefirmwarecurrenttbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    majorversion: Mapped[int] = mapped_column(Integer)
    minorversion: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    releasetrack: Mapped[int] = mapped_column(SmallInteger)
    ismfg: Mapped[bool] = mapped_column(Boolean)
    lastupdated: Mapped[datetime.datetime] = mapped_column(DateTime)

    devicestbl: Mapped["Devicestbl"] = relationship(
        "Devicestbl", back_populates="devicefirmwarecurrenttbl"
    )


class Devicestatustbl(Devicestbl):
    __tablename__ = "devicestatustbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("deviceid", name="devicestatustbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lastboottime: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        server_default=text("'1970-01-01 00:00:00'::timestamp without time zone"),
    )
    lastpostime: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        server_default=text("'1970-01-01 00:00:00'::timestamp without time zone"),
    )
    lastcommfailtime: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        server_default=text("'1970-01-01 00:00:00'::timestamp without time zone"),
    )
    lastappfailtime: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        server_default=text("'1970-01-01 00:00:00'::timestamp without time zone"),
    )
    latitude: Mapped[float] = mapped_column(Double(53), server_default=text("0"))
    longitude: Mapped[float] = mapped_column(Double(53), server_default=text("0"))
    gpsaltitude: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    horizontalaccuracy: Mapped[int] = mapped_column(
        SmallInteger, server_default=text("0")
    )
    verticalaccuracy: Mapped[int] = mapped_column(
        SmallInteger, server_default=text("0")
    )
    battpercent: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    battvoltage: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    updatereason: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    bootreason: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    hascommhwfail: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    hasapphwfail: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    emereventid: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    posrecordid: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    commhwfailrecordid: Mapped[int] = mapped_column(
        BigInteger, server_default=text("0")
    )
    apphwfailrecordid: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    bootrecordid: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))


class Devicetransferstbl(Devicestbl):
    __tablename__ = "devicetransferstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        ForeignKeyConstraint(
            ["targetid"],
            ["devicetransfertargetstbl.targetid"],
            name="fk_devicetransfertargets",
        ),
        PrimaryKeyConstraint("deviceid", name="devicetransferstbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    targetid: Mapped[int] = mapped_column(BigInteger)
    isacked: Mapped[bool] = mapped_column(Boolean)
    timeenacted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timesenttodevice: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    timereturnedtoserver: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    devicetransfertargetstbl: Mapped["Devicetransfertargetstbl"] = relationship(
        "Devicetransfertargetstbl", back_populates="devicetransferstbl"
    )


class Fuotaplanstagestbl(Base):
    __tablename__ = "fuotaplanstagestbl"
    __table_args__ = (
        ForeignKeyConstraint(["planid"], ["fuotaplanstbl.planid"], name="fk_planid"),
        PrimaryKeyConstraint("planid", "updatestage", name="fuotaplanstagestbl_pkey"),
    )

    planid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    updatestage: Mapped[int] = mapped_column(Integer, primary_key=True)
    stagedesc: Mapped[str] = mapped_column(String(256))
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime)
    skippable: Mapped[bool] = mapped_column(Boolean)

    fuotaplanstbl: Mapped["Fuotaplanstbl"] = relationship(
        "Fuotaplanstbl", back_populates="fuotaplanstagestbl"
    )


class Fuotaplanstagetargetstbl(Base):
    __tablename__ = "fuotaplanstagetargetstbl"
    __table_args__ = (
        ForeignKeyConstraint(["planid"], ["fuotaplanstbl.planid"], name="fk_planid"),
        PrimaryKeyConstraint(
            "planid", "updatestage", "appid", name="fuotaplanstagetargetstbl_pkey"
        ),
    )

    planid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    updatestage: Mapped[int] = mapped_column(Integer, primary_key=True)
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    releasetrack: Mapped[int] = mapped_column(SmallInteger)
    ismfg: Mapped[bool] = mapped_column(Boolean)
    majorversion: Mapped[int] = mapped_column(Integer)
    minorversion: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    updateorder: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    fuotaplanstbl: Mapped["Fuotaplanstbl"] = relationship(
        "Fuotaplanstbl", back_populates="fuotaplanstagetargetstbl"
    )


class Fuotasettingsperdevicetbl(Devicestbl):
    __tablename__ = "fuotasettingsperdevicetbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        ForeignKeyConstraint(["planid"], ["fuotaplanstbl.planid"], name="fk_planid"),
        PrimaryKeyConstraint("deviceid", name="fuotasettingsperdevicetbl_pkey"),
    )

    deviceid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planid: Mapped[int] = mapped_column(BigInteger)
    enablefuota: Mapped[bool] = mapped_column(Boolean)
    maxstage: Mapped[int] = mapped_column(Integer)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)

    fuotaplanstbl: Mapped["Fuotaplanstbl"] = relationship(
        "Fuotaplanstbl", back_populates="fuotasettingsperdevicetbl"
    )


class Fuotasettingsperdevicetypetbl(Base):
    __tablename__ = "fuotasettingsperdevicetypetbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["devicetypeid", "devicevariantid"],
            [
                "devicetypevarianttbl.devicetypeid",
                "devicetypevarianttbl.devicevariantid",
            ],
            name="fk_devicetype",
        ),
        ForeignKeyConstraint(["planid"], ["fuotaplanstbl.planid"], name="fk_planid"),
        PrimaryKeyConstraint(
            "devicetypeid",
            "devicevariantid",
            "accountid",
            name="fuotasettingsperdevicetypetbl_pkey",
        ),
    )

    devicetypeid: Mapped[int] = mapped_column(Integer, primary_key=True)
    devicevariantid: Mapped[int] = mapped_column(Integer, primary_key=True)
    accountid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planid: Mapped[int] = mapped_column(BigInteger)
    enablefuota: Mapped[bool] = mapped_column(Boolean)
    maxstage: Mapped[int] = mapped_column(Integer)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    lastmodified: Mapped[datetime.datetime] = mapped_column(DateTime)

    devicetypevarianttbl: Mapped["Devicetypevarianttbl"] = relationship(
        "Devicetypevarianttbl", back_populates="fuotasettingsperdevicetypetbl"
    )
    fuotaplanstbl: Mapped["Fuotaplanstbl"] = relationship(
        "Fuotaplanstbl", back_populates="fuotasettingsperdevicetypetbl"
    )


class Loginpermissiongrantshistorytbl(Base):
    __tablename__ = "loginpermissiongrantshistorytbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loginid"], ["loginstbl.loginid"], name="fk_loginstbl_id"
        ),
        ForeignKeyConstraint(
            ["permissionid"],
            ["permissionstbl.permissionid"],
            name="fk_permissionstbl_id",
        ),
        PrimaryKeyConstraint("recordid", name="loginpermissiongrantshistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(
        BigInteger,
        Identity(
            start=1,
            increment=1,
            minvalue=1,
            maxvalue=9223372036854775807,
            cycle=False,
            cache=1,
        ),
        primary_key=True,
    )
    loginid: Mapped[int] = mapped_column(BigInteger)
    permissionid: Mapped[int] = mapped_column(BigInteger)
    timegranted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timerevoked: Mapped[datetime.datetime] = mapped_column(DateTime)

    loginstbl: Mapped["Loginstbl"] = relationship(
        "Loginstbl", back_populates="loginpermissiongrantshistorytbl"
    )
    permissionstbl: Mapped["Permissionstbl"] = relationship(
        "Permissionstbl", back_populates="loginpermissiongrantshistorytbl"
    )


class Loginpermissiongrantstbl(Base):
    __tablename__ = "loginpermissiongrantstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loginid"], ["loginstbl.loginid"], name="fk_loginstbl_id"
        ),
        ForeignKeyConstraint(
            ["permissionid"],
            ["permissionstbl.permissionid"],
            name="fk_permissionstbl_id",
        ),
        PrimaryKeyConstraint(
            "loginid", "permissionid", name="loginpermissiongrantstbl_pkey"
        ),
    )

    loginid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    permissionid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timegranted: Mapped[datetime.datetime] = mapped_column(DateTime)

    loginstbl: Mapped["Loginstbl"] = relationship(
        "Loginstbl", back_populates="loginpermissiongrantstbl"
    )
    permissionstbl: Mapped["Permissionstbl"] = relationship(
        "Permissionstbl", back_populates="loginpermissiongrantstbl"
    )


class Loginrolegrantshistorytbl(Base):
    __tablename__ = "loginrolegrantshistorytbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loginid"], ["loginstbl.loginid"], name="fk_loginstbl_id"
        ),
        ForeignKeyConstraint(["roleid"], ["rolestbl.roleid"], name="fk_rolestbl_id"),
        PrimaryKeyConstraint("recordid", name="loginrolegrantshistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(
        BigInteger,
        Identity(
            start=1,
            increment=1,
            minvalue=1,
            maxvalue=9223372036854775807,
            cycle=False,
            cache=1,
        ),
        primary_key=True,
    )
    loginid: Mapped[int] = mapped_column(BigInteger)
    roleid: Mapped[int] = mapped_column(BigInteger)
    timegranted: Mapped[datetime.datetime] = mapped_column(DateTime)
    timerevoked: Mapped[datetime.datetime] = mapped_column(DateTime)

    loginstbl: Mapped["Loginstbl"] = relationship(
        "Loginstbl", back_populates="loginrolegrantshistorytbl"
    )
    rolestbl: Mapped["Rolestbl"] = relationship(
        "Rolestbl", back_populates="loginrolegrantshistorytbl"
    )


class Loginrolegrantstbl(Base):
    __tablename__ = "loginrolegrantstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loginid"], ["loginstbl.loginid"], name="fk_loginstbl_id"
        ),
        ForeignKeyConstraint(["roleid"], ["rolestbl.roleid"], name="fk_rolestbl_id"),
        PrimaryKeyConstraint("loginid", "roleid", name="loginrolegrantstbl_pkey"),
    )

    loginid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    roleid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timegranted: Mapped[datetime.datetime] = mapped_column(DateTime)

    loginstbl: Mapped["Loginstbl"] = relationship(
        "Loginstbl", back_populates="loginrolegrantstbl"
    )
    rolestbl: Mapped["Rolestbl"] = relationship(
        "Rolestbl", back_populates="loginrolegrantstbl"
    )


class Loginshistorytbl(Loginstbl):
    __tablename__ = "loginshistorytbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loginid"], ["loginstbl.loginid"], name="fk_loginstbl_id"
        ),
        PrimaryKeyConstraint("loginid", name="loginshistorytbl_pkey"),
    )

    recordid: Mapped[int] = mapped_column(
        BigInteger,
        Identity(
            start=1,
            increment=1,
            minvalue=1,
            maxvalue=9223372036854775807,
            cycle=False,
            cache=1,
        ),
    )
    loginid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    accountid: Mapped[int] = mapped_column(BigInteger)
    isactive: Mapped[bool] = mapped_column(Boolean)
    isprivileged: Mapped[bool] = mapped_column(Boolean)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    timearchived: Mapped[datetime.datetime] = mapped_column(DateTime)
    notes: Mapped[str] = mapped_column(String(64))


class Socketserversessionstbl(Base):
    __tablename__ = "socketserversessionstbl"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deviceid"], ["devicestbl.deviceid"], name="fk_devicestbl_id"
        ),
        PrimaryKeyConstraint("sessionid", name="socketserversessionstbl_pkey"),
        UniqueConstraint("deviceid", name="socketserversessionstbl_deviceid_key"),
    )

    sessionid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deviceid: Mapped[int] = mapped_column(BigInteger)
    lastpacketid: Mapped[int] = mapped_column(BigInteger)
    timecreated: Mapped[datetime.datetime] = mapped_column(DateTime)
    aeskeycipher: Mapped[str] = mapped_column(String(64))
    mackeycipher: Mapped[str] = mapped_column(String(64))

    devicestbl: Mapped["Devicestbl"] = relationship(
        "Devicestbl", back_populates="socketserversessionstbl"
    )

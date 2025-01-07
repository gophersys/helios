import asyncio
from prisma import Prisma, Json


# Function to seed the database
async def seed():
    # Initialize the Prisma client
    db = Prisma()
    await db.connect()

    # Platform seeding
    platform_alpha = await db.platform.create(data={"name": "alpha"})
    platform_sigma5 = await db.platform.create(data={"name": "sigma5"})

    # HardwareVersion seeding
    hw_alpha_b0 = await db.hardwareversion.create(
        data={"version": "B0", "platform": {"connect": {"id": platform_alpha.id}}}
    )
    hw_sigma5_c1 = await db.hardwareversion.create(
        data={"version": "C1", "platform": {"connect": {"id": platform_sigma5.id}}}
    )

    # FirmwareVersion seeding
    firmware_1_2_0 = await db.firmwareversion.create(
        data={
            "version": "1.2.0",
            "hardwareVersions": {"connect": [{"id": hw_alpha_b0.id}]},  # Direct connection to HardwareVersion
        }
    )
    firmware_2_1_2 = await db.firmwareversion.create(
        data={
            "version": "2.1.2",
            "hardwareVersions": {"connect": [{"id": hw_sigma5_c1.id}]},  # Direct connection to HardwareVersion
        }
    )

    # Host seeding
    host_nrf9160 = await db.host.create(
        data={
            "name": "nrf9160",
            "hardwareVersions": {"connect": [{"id": hw_alpha_b0.id}]},  # Direct connection to HardwareVersion
        }
    )
    host_nrf52840 = await db.host.create(
        data={
            "name": "nrf52840",
            "hardwareVersions": {"connect": [{"id": hw_sigma5_c1.id}]},  # Direct connection to HardwareVersion
        }
    )

    # SocketServerVersion seeding (Note the use of JSON-compatible dictionaries)
    socket_version_0_9 = await db.socketserverversion.create(
        data={
            "version": "0.9",
            "messages": Json(data={"connectMessage": "Socket connected", "disconnectMessage": "Socket disconnected"}),
            "firmwareVersions": {"connect": [{"id": firmware_1_2_0.id}]},  # Direct connection to FirmwareVersion
        }
    )
    socket_version_1_0 = await db.socketserverversion.create(
        data={
            "version": "1.0",
            "messages": Json(
                data={
                    "connectMessage": "Socket connection established",
                    "disconnectMessage": "Socket connection closed",
                }
            ),
            "firmwareVersions": {"connect": [{"id": firmware_2_1_2.id}]},  # Direct connection to FirmwareVersion
        }
    )

    # Disconnect after seeding
    await db.disconnect()


# Running the seed function
if __name__ == "__main__":
    asyncio.run(seed())

//=================================================================================================
//Global variable
//=================================================================================================
bool _sensor_operation = true; // control by host

//=================================================================================================
//I2C control function phototypes. 
//=================================================================================================
void I2C_WriteReg(UNS_8 addr, UNS_8 data);
void I2C_ReadReg(UNS_8 addr, UNS_8 *pData);
void I2C_ReadMultiReg(UNS_8 addr, UNS_8 *pData, UNS_8 length);

//=================================================================================================
//Part ID check.
//=================================================================================================
void ThermoPartIdCheck(void)
{
	UNS_8 u8IdL = 0;
	UNS_8 u8IdH = 0;
	UNS_16 u16Id = 0;

	do 
	{
		// delay 120ms
		Sleep(120);

		// switch to Bank0 Register
		I2C_WriteReg(0x7f, 0x00) ;

		// read ID 		
		I2C_ReadReg(0x00, &u8IdL) ;	
		I2C_ReadReg(0x01, &u8IdH) ;
		u16Id = u8IdH*256 + u8IdL;
	}
	while (u16Id != 0x0271);
}

//=================================================================================================
//Sensor register settings initialization process.
//=================================================================================================
void ThermoInit(void)
{
	UNS_8 u8OTPLoadDone = 0;
	UNS_8 u8StatusFlag = 0;

	// switch to Bank0 Register
	I2C_WriteReg(0x7f, 0x00) ;	
	
	// cold reset
	I2C_WriteReg(0x7d, 0x5a) ;	

	do
	{
		// delay 120ms
		Sleep(120);	

		// read status flag
		I2C_ReadReg(0x05, &u8StatusFlag) ;

		// get otp_load_done flag from status flag
		u8OTPLoadDone = (u8StatusFlag >> 6) & 0x01;	
	}
	while(u8OTPLoadDone != 1);

}

//=================================================================================================
//Sensor register settings initialization process.
//=================================================================================================
void ThermoCustomize(void)
{
	// switch to Bank0 Register
	I2C_WriteReg(0x7f, 0x00) ;

	// set Over Sampling	
	I2C_WriteReg(0x20, 0xAD) ;

	// set report rate to 1Hz	
	I2C_WriteReg(0x21, 0xe2) ;		
	I2C_WriteReg(0x22, 0x04) ;			
	I2C_WriteReg(0x23, 0x00) ;	

	// switch to Bank1 Register
	I2C_WriteReg(0x7f, 0x01) ;

	// set compensate parameter	
	I2C_WriteReg(0x50, 0x62) ;	
	I2C_WriteReg(0x51, 0x21) ;	
}

//=================================================================================================
//Sensor operation enable
//=================================================================================================
void ThermoEnable()
{
	// switch to Bank0 Register
	I2C_WriteReg(0x7f, 0x00) ;	
	
	// output enable
	I2C_WriteReg(0x04, 0x01) ;			
	
}
//=================================================================================================
//Sensor operation disable
//=================================================================================================
void ThermoDisable()
{	
	// switch to Bank0 Register
	I2C_WriteReg(0x7f, 0x00) ;	
	
	// output disable
	I2C_WriteReg(0x04, 0x00) ;			
}
//=================================================================================================
//Sensor data read and temperature calculation
//1. Polling read "Alert_flag" and check if the conversion data are available to read.
//   if Alert_flag=1, read Ta and To temperature data in register 0x0A to 0x0D and status flag in 
//   register 0x05.
//2. After read temperature data, check "DataOverflow flag"=0 to confirm conversion data are valid. 
//   if data are invalid, please ignore this data and wait next alert flag.
//3. The Ta and To temperature data are in 16 bits 2's complement format and 0.03125degree/code.
//=================================================================================================
bool ThermoRead(double *pTa, double *pTo)
{
	UNS_8 u8ThermoData[4] = {0};	
	UNS_8 u8AlertFlag = 0;
	UNS_8 u8DataOverflow = 0;
	UNS_8 u8StatusFlag = 0;
	INT_16 s16CAL_TaData = 0;
	INT_16 s16CAL_ToData = 0;

	// switch to Bank0 Register
	I2C_WriteReg(0x7f, 0x00) ;	
		
	// read status flag
	I2C_ReadReg(0x05, &u8StatusFlag) ;

	// get alert flag from status flag
	u8AlertFlag = u8StatusFlag & 0x01;
	
	if(u8AlertFlag == 0x01) 
	{		
		// read 4 bytes thermo data		
		I2C_ReadMultiReg(0x0a, u8ThermoData, 4) ;
	
		// get data overflow from status flag
		u8DataOverflow = (u8StatusFlag >> 7) & 0x01;		
		
		if(u8DataOverflow == 0)			
		{
			// valid thermo data
			s16CAL_TaData = (INT_16)(u8ThermoData[1] * 256 + u8ThermoData[0]);
			s16CAL_ToData = (INT_16)(u8ThermoData[3] * 256 + u8ThermoData[2]);
			
			*pTa = s16CAL_TaData / 32.0;	
			*pTo = s16CAL_TaData / 32.0;	

			return true;	
		}					
	}	
	return false;
}

//=================================================================================================
//1. If stop to conversion, please set "_sensor_operation" to False to stop conversion.
//=================================================================================================
void main(void)
{
	double ta = 0;
	double to = 0;
	
	ThermoPartIdCheck();

	ThermoInit();

	ThermoCustomize();
		
	ThermoEnable();
	
	while(_sensor_operation)
	{
		if(ThermoRead(&ta, &to))
		{		
			// valid temperature data
			// code your application's behavior here.
			printf("Ta = %f  To = %f\r\n", ta, to);
		}
		// delay 125ms
		Sleep(125);

	}	
	
	ThermoDisable();
	
}
using System;
using System.Collections.Generic;
using System.Threading;
using LibCommon.Model;
using LibCommon.Utils;
using SharpDX.XInput;

namespace LibCommon.Command;

public class DongleCommand
{
	public static int MaxLengthEveryParcel = 10;

	public static byte MaxLengthPerPackageDataWired = 20;

	public static byte K2MaxLengthPerPackageDataWired = 64;

	public static int perPackageLength = MaxLengthEveryParcel;

	public static byte[] GetFlashSaveConfigCmd(byte[] arrs)
	{
		byte[] array = new byte[perPackageLength + 5];
		array[0] = 5;
		array[1] = 80;
		array[2] = 3;
		array[3] = arrs[0];
		array[4] = arrs[1];
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[5] += array[i];
		}
		return array;
	}

	public static byte[] GetReadRandomInfoCmd(byte cfgID)
	{
		byte[] array = new byte[perPackageLength + 4];
		array[0] = 5;
		array[1] = 80;
		array[2] = 2;
		array[3] = cfgID;
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] getUpdatePartlyStartCommand(int startPkgIndex, int startPkgLen)
	{
		byte[] array = new byte[perPackageLength + 4];
		array[0] = 5;
		array[1] = 239;
		array[2] = (byte)startPkgIndex;
		array[3] = (byte)startPkgLen;
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] getStartCommand(int length, byte configId)
	{
		byte[] array = new byte[perPackageLength + 4];
		array[0] = 5;
		array[1] = 234;
		array[2] = (byte)length;
		array[3] = 160;
		array[4] = configId;
		return array;
	}

	public static byte[] getStartLEDCommand(int length, byte configId)
	{
		byte[] array = new byte[perPackageLength + 4];
		array[0] = 5;
		array[1] = 231;
		array[2] = configId;
		array[3] = (byte)length;
		return array;
	}

	public static byte[] getStartFlashCommand(int startIndex, int pkgLength, byte configId)
	{
		byte[] array = new byte[perPackageLength + 4];
		array[0] = 5;
		array[1] = 239;
		array[2] = (byte)startIndex;
		array[3] = (byte)pkgLength;
		array[4] = 160;
		array[5] = configId;
		return array;
	}

	public static byte[] getStartFlashLEDCommand(int startIndex, int pkgLength, byte configId)
	{
		byte[] array = new byte[perPackageLength + 5];
		array[0] = 5;
		array[1] = 230;
		array[2] = configId;
		array[3] = (byte)startIndex;
		array[4] = (byte)pkgLength;
		return array;
	}

	public static byte[] getStartCommand(int length)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 234;
		array[2] = (byte)length;
		return array;
	}

	public static byte[] getUpdateCommand(int length, int partlyID, int parcelCount)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 239;
		switch (partlyID)
		{
		case 1:
			array[2] = 3;
			break;
		case 2:
			array[2] = 4;
			break;
		case 3:
			array[2] = 5;
			break;
		case 4:
			array[2] = 6;
			break;
		}
		array[3] = (byte)parcelCount;
		return array;
	}

	public static byte[] getUpdateCommandAutoTrigger(int partlyID, int parcelCount, byte isSave = 0)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 239;
		switch (partlyID)
		{
		case 1:
			array[2] = 3;
			break;
		case 2:
			array[2] = 4;
			break;
		case 3:
			array[2] = 5;
			break;
		case 4:
			array[2] = 52;
			break;
		}
		array[3] = (byte)parcelCount;
		array[4] = isSave;
		return array;
	}

	public static byte[] GetSoftUpgradeCmd(byte McuType)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 245;
		switch (McuType)
		{
		case 71:
			array[2] = 4;
			break;
		case 113:
			array[1] = 246;
			array[2] = 1;
			break;
		case 115:
			array[2] = 3;
			break;
		case 130:
			array[2] = 3;
			break;
		case 1:
			array[2] = 3;
			break;
		case 2:
			array[1] = 246;
			array[2] = 1;
			break;
		}
		return array;
	}

	public static byte[] getReadConfigCommand(int configId)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 235;
		array[2] = (byte)configId;
		return array;
	}

	public static byte[] getReadLEDConfigCommand(int configId)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 229;
		array[2] = (byte)configId;
		return array;
	}

	public static byte[] getSwitchOriginData(bool state)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 238;
		array[2] = (state ? ((byte)1) : ((byte)0));
		return array;
	}

	public static byte[] getSwitchAndroid2XInput()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 237;
		return array;
	}

	public static byte[] getSwitchAndroid2OTA()
	{
		byte[] array = new byte[perPackageLength + 3];
		array[0] = 5;
		array[1] = 245;
		array[2] = 7;
		return array;
	}

	public static byte[] getDeviceInfoInAndroid()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 236;
		return array;
	}

	public static byte[] getK1ExtensionChipInfo()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 245;
		array[2] = 1;
		return array;
	}

	public static byte[] getTestRGBCommand(int r, int g, int b)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 224;
		array[2] = (byte)r;
		array[3] = (byte)g;
		array[4] = (byte)b;
		return array;
	}

	public static byte[] getTestLedCommand(int led_id)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 227;
		array[2] = (byte)led_id;
		array[3] = 2;
		array[4] = 1;
		return array;
	}

	public static byte[] getTestMotorCommand(int left, int right)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 15;
		array[2] = (byte)left;
		array[3] = (byte)right;
		return array;
	}

	public static byte[] getTestMotorCommand()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 15;
		array[2] = 112;
		array[3] = 112;
		return array;
	}

	public static byte[] getTestMotorCommandStrong()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 15;
		array[2] = byte.MaxValue;
		array[3] = byte.MaxValue;
		return array;
	}

	public static byte[] getDongleVersionCommand()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 17;
		return array;
	}

	public static byte[] getTestJoystickResetCommand()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 226;
		return array;
	}

	public static byte[] getTestNewJoystickResetCommand(byte d)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 226;
		array[2] = d;
		return array;
	}

	public static byte[] getStopMacroActionCommand()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 233;
		return array;
	}

	public static bool SwitchXInput2Android()
	{
		Controller[] array = new Controller[4]
		{
			new Controller(UserIndex.One),
			new Controller(UserIndex.Two),
			new Controller(UserIndex.Three),
			new Controller(UserIndex.Four)
		};
		Controller controller = null;
		List<Controller> list = new List<Controller>();
		int num = 3;
		while (num > 0)
		{
			Controller[] array2 = array;
			foreach (Controller controller2 in array2)
			{
				if (controller2.IsConnected)
				{
					FLog.d("XInputConnected: " + controller2.UserIndex);
					controller = controller2;
					list.Add(controller);
				}
			}
			num--;
			FLog.d("SwitchXInput2Android wait");
			Thread.Sleep(100);
		}
		if (controller == null)
		{
			FLog.d("SwitchXInput2Android controller == null");
		}
		else if (!controller.IsConnected)
		{
			FLog.d("SwitchXInput2Android controller.IsConnected = false");
		}
		if (list.Count > 0)
		{
			foreach (Controller item in list)
			{
				if (item.IsConnected)
				{
					FLog.d("controller.IsConnected !!!!!!!!!!!!!!!!!!");
					try
					{
						int num2 = 43520;
						int num3 = 47872;
						Vibration vibration = new Vibration
						{
							LeftMotorSpeed = (ushort)num2,
							RightMotorSpeed = (ushort)num3
						};
						item.SetVibration(vibration);
						Thread.Sleep(100);
						vibration.LeftMotorSpeed = (ushort)num3;
						vibration.RightMotorSpeed = (ushort)num2;
						item.SetVibration(vibration);
						Thread.Sleep(100);
						vibration.LeftMotorSpeed = (ushort)num2;
						vibration.RightMotorSpeed = (ushort)num3;
						item.SetVibration(vibration);
						Thread.Sleep(100);
						vibration.LeftMotorSpeed = 0;
						vibration.RightMotorSpeed = 0;
						item.SetVibration(vibration);
					}
					catch (Exception)
					{
					}
				}
			}
		}
		return true;
	}

	public static bool XInputRestart()
	{
		Controller[] array = new Controller[4]
		{
			new Controller(UserIndex.One),
			new Controller(UserIndex.Two),
			new Controller(UserIndex.Three),
			new Controller(UserIndex.Four)
		};
		Controller controller = null;
		int num = 3;
		while (num > 0)
		{
			Controller[] array2 = array;
			foreach (Controller controller2 in array2)
			{
				if (controller2.IsConnected)
				{
					FLog.d("XInputConnected: " + controller2.UserIndex);
					controller = controller2;
					break;
				}
			}
			if (controller != null)
			{
				break;
			}
			num--;
			FLog.d("XInputRestart wait");
			Thread.Sleep(100);
		}
		if (controller == null)
		{
			FLog.d("XInputRestart controller == null");
		}
		else if (!controller.IsConnected)
		{
			FLog.d("XInputRestart controller.IsConnected = false");
		}
		if (controller != null && controller.IsConnected)
		{
			FLog.d("controller.IsConnected !!!!!!!!!!!!!!!!!!");
			try
			{
				int num2 = 43776;
				int num3 = 47616;
				Vibration vibration = new Vibration
				{
					LeftMotorSpeed = (ushort)num2,
					RightMotorSpeed = (ushort)num3
				};
				controller.SetVibration(vibration);
				Thread.Sleep(100);
				num2 = 47616;
				num3 = 43776;
				vibration.LeftMotorSpeed = (ushort)num2;
				vibration.RightMotorSpeed = (ushort)num3;
				controller.SetVibration(vibration);
				Thread.Sleep(100);
				num2 = 43776;
				num3 = 47616;
				vibration.LeftMotorSpeed = (ushort)num2;
				vibration.RightMotorSpeed = (ushort)num3;
				controller.SetVibration(vibration);
				Thread.Sleep(100);
				num2 = 0;
				num3 = 0;
				vibration.LeftMotorSpeed = 0;
				vibration.RightMotorSpeed = 0;
				controller.SetVibration(vibration);
			}
			catch
			{
			}
		}
		return true;
	}

	public static byte[] getSTDControl(bool state)
	{
		return new byte[12]
		{
			5,
			16,
			(!state) ? ((byte)1) : ((byte)0),
			(!state) ? ((byte)1) : ((byte)0),
			(!state) ? ((byte)1) : ((byte)0),
			0,
			0,
			0,
			0,
			0,
			0,
			0
		};
	}

	public static byte[] getDInputRestartCmd()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 244;
		return array;
	}

	public static byte[] getCurrentConfigIdCommand()
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 235;
		array[2] = 160;
		return array;
	}

	public static byte[] getTriggerSECommand(byte subCmd)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 243;
		array[2] = subCmd;
		for (int i = 0; i < 3; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] getLedPicUpdateStartCommand(byte SType, byte picWidth, byte picHeight, byte picNum, byte picFreq = 10, byte exchangeAll = 0)
	{
		byte[] array = new byte[10] { 5, 240, SType, picWidth, picHeight, picNum, picFreq, MaxLengthPerPackageDataWired, exchangeAll, 0 };
		for (int i = 2; i < array.Length - 1; i++)
		{
			array[9] += array[i];
		}
		return array;
	}

	public static byte[] GetK2LedStartPicCmd(byte[] cmdParam)
	{
		byte[] array = new byte[12]
		{
			5,
			165,
			208,
			9,
			cmdParam[0],
			cmdParam[1],
			cmdParam[2],
			cmdParam[3],
			cmdParam[4],
			cmdParam[5],
			cmdParam[6],
			0
		};
		for (int i = 2; i < array.Length - 1; i++)
		{
			array[11] += array[i];
		}
		return array;
	}

	public static byte[] getLedPicUpdateEndCommand(byte SIndex)
	{
		byte[] array = new byte[4] { 5, 241, SIndex, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] getK2LedPicUpdateEndCommand(byte picId, long totalSize, byte picIndex = 1)
	{
		byte[] array = new byte[10] { 90, 165, 210, 9, picId, picIndex, 0, 0, 0, 0 };
		byte b = (byte)(totalSize >> 8);
		byte b2 = (byte)(totalSize & 0xF);
		array[6] = b;
		array[7] = b2;
		array[8] = 0;
		array[9] = 0;
		for (int i = 2; i < array.Length - 1; i++)
		{
			array[9] += array[i];
		}
		return array;
	}

	public static byte[] getLedPicUpdateDataCommand(byte cmdId)
	{
		byte[] array = new byte[MaxLengthPerPackageDataWired];
		array[0] = 5;
		array[1] = cmdId;
		return array;
	}

	public static byte[] getLedStandbyCommand(byte SleepInterval)
	{
		byte[] array = new byte[5] { 5, 242, 2, SleepInterval, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] getUUIDCommand()
	{
		byte[] array = new byte[5] { 5, 250, 160, 0, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] getScreenSleepTimeCmd()
	{
		byte[] array = new byte[4] { 5, 242, 3, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] getGamepadMapConfigCmd()
	{
		byte[] array = new byte[4] { 5, 80, 6, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] getAllFuncSetConfigCmd()
	{
		byte[] array = new byte[4] { 5, 80, 6, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] GetSwitchConfigCmd(int configId)
	{
		byte[] array = new byte[5]
		{
			5,
			80,
			5,
			(byte)configId,
			0
		};
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] GetSwitchConfigCmd(byte SwitchData)
	{
		byte[] array = new byte[5] { 5, 250, 162, SwitchData, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] GetSetTriggerEliminateJitterCmd(byte SwitchData)
	{
		byte[] array = new byte[5] { 5, 80, 7, SwitchData, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] GetSetJoyAutoCorrectCmd(byte SwitchData)
	{
		byte[] array = new byte[5] { 5, 80, 8, SwitchData, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] GetSetFuncConfigCmd(byte setType, byte setValue)
	{
		byte[] array = new byte[5] { 5, 80, setType, setValue, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] GetSwitchMapConfigCmd(byte SwitchData)
	{
		byte[] array = new byte[5] { 5, 80, 5, SwitchData, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] GetCalibrationCmd(byte status)
	{
		byte[] array = new byte[5] { 5, 226, status, 0, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] getScreenStatusBarCmd()
	{
		byte[] array = new byte[4] { 5, 242, 3, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] getStatusBarSetCommand(byte EnableStatusbar)
	{
		byte[] array = new byte[5] { 5, 242, 1, EnableStatusbar, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] getBurstSetCommand(byte keyId, byte triggerType, byte frequence)
	{
		byte[] array = new byte[7] { 5, 242, 4, keyId, triggerType, frequence, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[6] += array[i];
		}
		return array;
	}

	public static byte[] getBurstSetCommand(KeyBurstModel keyBurstInfo)
	{
		byte[] array = new byte[7] { 5, 242, 4, keyBurstInfo.KeyId, keyBurstInfo.TriggerType, keyBurstInfo.Frequence, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[6] += array[i];
		}
		return array;
	}

	public static byte[] getBurstCommand(byte keyId)
	{
		byte[] array = new byte[5] { 5, 242, 4, keyId, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[4] += array[i];
		}
		return array;
	}

	public static byte[] SetTriggerParams(byte ApplyMode, byte TriggerType, byte Mode, byte[] Params)
	{
		byte[] array = new byte[12];
		if (Params.Length <= 3)
		{
			return array;
		}
		array[0] = 5;
		array[1] = 160;
		array[2] = 1;
		array[3] = ApplyMode;
		array[4] = TriggerType;
		array[5] = Mode;
		array[6] = Params[0];
		array[7] = Params[1];
		array[8] = Params[2];
		array[9] = Params[3];
		array[10] = Params[4];
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[11] += array[i];
		}
		return array;
	}

	public static byte[] GetTriggerParams()
	{
		byte[] array = new byte[4] { 5, 160, 2, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] getScreenTestCmd()
	{
		byte[] array = new byte[4] { 5, 160, 3, 0 };
		for (int i = 0; i < array.Length - 1; i++)
		{
			array[3] += array[i];
		}
		return array;
	}

	public static byte[] SetK1SpaceFlight()
	{
		return new byte[4] { 5, 245, 5, 26 };
	}

	public static byte[] SetK1DeviceId(byte deviceId)
	{
		return new byte[4] { 5, 245, 5, deviceId };
	}

	public static byte[] SetK1Pirate()
	{
		return new byte[4] { 5, 245, 5, 29 };
	}

	public static byte[] SetDeviceIdIP(byte deviceId)
	{
		return new byte[4] { 5, 245, 5, deviceId };
	}

	public static byte[] GetK1TempAutoTrigger(byte TriggerType, byte[] paramsArr)
	{
		return SetTriggerParams(Params: new byte[5]
		{
			paramsArr[1],
			paramsArr[2],
			paramsArr[3],
			paramsArr[4],
			paramsArr[5]
		}, ApplyMode: 0, TriggerType: TriggerType, Mode: paramsArr[0]);
	}

	public static byte[] GetPS5ModeCommand(byte mode)
	{
		byte[] array = new byte[perPackageLength + 2];
		array[0] = 5;
		array[1] = 232;
		array[2] = 1;
		array[3] = mode;
		return array;
	}
}

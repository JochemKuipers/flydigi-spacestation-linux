using LibCommon.Model;

namespace LibCommon.Command;

public class XinputCommand
{
	public static int PerPicPackageMaxLength = 24;

	public static byte MaxLengthPerPackageDataWired = 20;

	public static int PerPackageMaxLength = 15;

	public static int PerPackageDataLength = 10;

	public static int K2PerPackageDataLength = 26;

	public static byte[] getSendData(byte subCmd)
	{
		byte[] data = getData();
		data[1] = subCmd;
		return CrcData(data);
	}

	public static byte[] getSendData(byte subCmd, byte pArgs1)
	{
		byte[] data = getData();
		data[1] = subCmd;
		data[2] = pArgs1;
		return CrcData(data);
	}

	private static byte[] getPicSendData(byte subCmd, byte pArgs1)
	{
		byte[] picData = getPicData();
		picData[1] = subCmd;
		picData[2] = pArgs1;
		return CrcData(picData);
	}

	public static byte[] getSendData(byte subCmd, byte pArgs1, byte[] pArgs)
	{
		byte[] data = getData();
		data[1] = subCmd;
		data[2] = pArgs1;
		if (pArgs.Length > data.Length - 2)
		{
			return CrcData(data);
		}
		for (int i = 0; i < pArgs.Length; i++)
		{
			data[i + 3] = pArgs[i];
		}
		return CrcData(data);
	}

	public static byte[] getStopKeyMapCmd()
	{
		return getSendData(CommandDic.SubCmdId["IsUseKeyMap"], 1);
	}

	public static byte[] getOpenKeyMapCmd()
	{
		return getSendData(CommandDic.SubCmdId["IsUseKeyMap"], 2);
	}

	public static byte[] GetSoftUpgradeCmd(byte McuType)
	{
		return McuType switch
		{
			71 => Get547UpgradeCmd(), 
			113 => Get571DongleUpgradeCmd(), 
			115 => Get582UpgradeCmd(), 
			130 => Get582UpgradeCmd(), 
			1 => GetFp1GamepadUpgradeCmd(), 
			2 => Get571DongleUpgradeCmd(), 
			_ => null, 
		};
	}

	public static byte[] Get547UpgradeCmd()
	{
		return getSendData(CommandDic.SubCmdId["WCH547UpgradeCmd"], 12);
	}

	public static byte[] Get582UpgradeCmd()
	{
		return getSendData(CommandDic.SubCmdId["WCH582UpgradeCmd"], 11);
	}

	public static byte[] GetFp1GamepadUpgradeCmd()
	{
		return getSendData(CommandDic.SubCmdId["KZGPUpgradeCmd"], 11);
	}

	public static byte[] Get571DongleUpgradeCmd()
	{
		return getSendData(CommandDic.SubCmdId["Dongle571UpgradeCmd"], 1);
	}

	public static byte[] getSendData(byte subCmd, byte[] pArgs)
	{
		byte[] data = getData();
		data[1] = subCmd;
		if (pArgs.Length > data.Length - 1)
		{
			return CrcData(data);
		}
		for (int i = 0; i < pArgs.Length; i++)
		{
			data[i + 2] = pArgs[i];
		}
		return CrcData(data);
	}

	public static byte[] getSendData(byte subCmd, byte[] pArgs, int packageIndex)
	{
		byte[] data = getData();
		data[1] = subCmd;
		if (pArgs.Length > data.Length - 1)
		{
			return CrcData(data);
		}
		for (int i = 0; i < pArgs.Length; i++)
		{
			data[i + 2] = pArgs[i];
		}
		data[12] = 160;
		data[13] = (byte)packageIndex;
		return CrcData(data);
	}

	public static byte[] getSendData(byte subCmd, byte pArgs1, byte pArgs2)
	{
		byte[] data = getData();
		data[1] = subCmd;
		data[2] = pArgs1;
		data[3] = pArgs2;
		return CrcData(data);
	}

	public static byte[] getSendData(byte subCmd, byte pArgs1, byte pArgs2, byte pArgs3)
	{
		byte[] data = getData();
		data[1] = subCmd;
		data[2] = pArgs1;
		data[3] = pArgs2;
		data[4] = pArgs3;
		return CrcData(data);
	}

	public static byte[] getK1PicPerDataCmd(byte SubCmdType)
	{
		return getPicSendData(CommandDic.SubCmdId["K1CmdID"], SubCmdType);
	}

	public static byte[] getK2PicPerDataCmd(byte SubCmdType)
	{
		byte[] array = new byte[64];
		array[0] = 90;
		array[1] = 165;
		array[2] = SubCmdType;
		CrcData(array);
		return array;
	}

	public static byte[] getK1Info(byte SubCmdType)
	{
		return getSendData(CommandDic.SubCmdId["K1CmdID"], SubCmdType);
	}

	public static byte[] getK1ExtInfo()
	{
		return getSendData(CommandDic.SubCmdId["K1CmdID"], 1);
	}

	public static byte[] getK1Info(byte SubCmdType, byte pArgs)
	{
		return getSendData(CommandDic.SubCmdId["K1CmdID"], SubCmdType, pArgs);
	}

	public static byte[] getK1Info(byte SubCmdType, byte[] setParams)
	{
		return getSendData(CommandDic.SubCmdId["K1CmdID"], SubCmdType, setParams);
	}

	public static byte[] setK1Info(byte SubCmdType, byte[] setParams)
	{
		return getSendData(CommandDic.SubCmdId["K1CmdID"], SubCmdType, setParams);
	}

	public static byte[] setK1Info(byte SubCmdType, byte setParam)
	{
		return getSendData(CommandDic.SubCmdId["K1CmdID"], SubCmdType, setParam);
	}

	public static byte[] getBurstSetCommand(byte keyId, byte triggerType, byte frequence)
	{
		return getSendData(pArgs: new byte[3] { keyId, triggerType, frequence }, subCmd: CommandDic.SubCmdId["BurstCmdID"], pArgs1: CommandDic.SubCmdId["SubCmdSETID"]);
	}

	public static byte[] getSwitchIPCommand(byte deviceId)
	{
		return getSendData(80, 15, new byte[3] { deviceId, 0, 0 });
	}

	public static byte[] getBurstSetCommand(KeyBurstModel keyBurstInfo)
	{
		return getSendData(pArgs: new byte[3] { keyBurstInfo.KeyId, keyBurstInfo.TriggerType, keyBurstInfo.Frequence }, subCmd: CommandDic.SubCmdId["BurstCmdID"], pArgs1: CommandDic.SubCmdId["SubCmdSETID"]);
	}

	public static byte[] getBurstCommand(byte keyId)
	{
		return getSendData(CommandDic.SubCmdId["BurstCmdID"], CommandDic.SubCmdId["SubCmdGETID"], keyId);
	}

	public static byte[] GetK1TempAutoTrigger(byte TriggerType, byte[] paramsArr)
	{
		byte[] result = new byte[11];
		if (paramsArr.Length != 6)
		{
			return result;
		}
		byte[] array = new byte[9];
		byte b = paramsArr[0];
		array[0] = 6;
		array[1] = 0;
		array[2] = TriggerType;
		array[3] = b;
		array[4] = paramsArr[1];
		array[5] = paramsArr[2];
		array[6] = paramsArr[3];
		array[7] = paramsArr[4];
		array[8] = paramsArr[5];
		return getSendData(CommandDic.SubCmdId["K1CmdID"], array);
	}

	public static byte[] GetGamePadMapConfigCmd(byte SubCmdType)
	{
		return getSendData(80, SubCmdType);
	}

	public static byte[] GetTriggerVibSetCmd(byte TriggerType, byte BindType, byte VibFilter, byte[] param, byte pwmScal = 10)
	{
		_ = new byte[11];
		byte b = 0;
		if (param != null)
		{
			b = (byte)param.Length;
		}
		byte[] array = new byte[10] { 8, TriggerType, BindType, VibFilter, pwmScal, 0, 0, 0, 0, 0 };
		if (b >= 0 && b <= 5)
		{
			for (int i = 0; i < b; i++)
			{
				array[5 + i] = param[i];
			}
		}
		return getSendData(CommandDic.SubCmdId["K1CmdID"], array);
	}

	private static byte[] getData()
	{
		byte[] array = new byte[PerPackageMaxLength];
		array[0] = 165;
		return array;
	}

	private static byte[] getPicData()
	{
		byte[] array = new byte[PerPicPackageMaxLength];
		array[0] = 165;
		return array;
	}

	public static byte[] CrcData(byte[] data)
	{
		return CrcData(data, 0);
	}

	public static byte[] CrcData(byte[] data, int start)
	{
		byte b = 0;
		for (int i = start; i < data.Length; i++)
		{
			if (i == data.Length - 1)
			{
				data[i] = b;
				break;
			}
			b += data[i];
		}
		return data;
	}
}

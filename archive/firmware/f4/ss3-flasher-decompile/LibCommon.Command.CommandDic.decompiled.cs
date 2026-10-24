using System.Collections.Generic;

namespace LibCommon.Command;

public static class CommandDic
{
	public static Dictionary<string, byte> SubCmdId;

	public const byte CmdPrefix = 165;

	public const byte GamePadInfo = 16;

	public const byte DongleInfo = 17;

	public const byte MotorShock = 18;

	public const byte LedTest = 19;

	public const byte JoystickReset = 20;

	public const byte LightTest = 21;

	public const byte Dormancy = 22;

	public const byte SwitchDinput = 23;

	public const byte IsUseKeyMap = 24;

	public const byte CloseMacro = 25;

	public const byte GetCurConfigId = 32;

	public const byte ReadConfigId = 33;

	public const byte KeyMapCfgReport = 34;

	public const byte StartFLashDataKMPC = 35;

	public const byte WriteDataKMPC = 36;

	public const byte StartKMPC = 37;

	public const byte StartFLashLEDDataKMPC = 40;

	public const byte TriggerMotorVib = 80;

	public const byte K1CmdID = 48;

	public const byte K1SubCmdExtInfo = 1;

	public const byte K1SubCmdScreenStatusBarInfo = 2;

	public const byte K1SubCmdScreenStatusBarSet = 3;

	public const byte K1SubCmdScreenSleepTimeInfo = 4;

	public const byte K1SubCmdScreenSleepTimeSet = 5;

	public const byte K1SubCmdScreenStartPic = 16;

	public const byte K1SubCmdScreenPicData = 17;

	public const byte K1SubCmdScreenEndPic = 18;

	public const byte CablirationFlag = 20;

	public const byte K2SubCmdScreenStartPic = 208;

	public const byte K2SubCmdScreenPicData = 209;

	public const byte K2SubCmdScreenEndPic = 210;

	public const byte K2SubCmdScreenEndPicAll = 211;

	public const byte K1SubCmdTriggerSet = 6;

	public const byte K1SubCmdTriggerInfo = 7;

	public const byte K1SubCmdSetTriggerVib = 8;

	public const byte Dongle571UpgradeCmd = 64;

	public const byte Dongle571UpgradeCmdSubCmd = 1;

	public const byte WCH582UpgradeCmd = 48;

	public const byte WCH582UpgradeCmdSubCmd = 11;

	public const byte KZGPUpgradeCmd = 48;

	public const byte KZGPUpgradeCmdSubCmd = 11;

	public const byte WCH547UpgradeCmd = 48;

	public const byte WCH547UpgradeCmdSubCmd = 12;

	public const byte XinputToOTACmd = 15;

	public const byte SpecifyConfigId = 160;

	public const byte ReadLedConfigById = 38;

	public const byte ReadLedCBCmd = 39;

	public const byte StartWriteLed = 42;

	public const byte WriteLed = 41;

	public const byte UUID = 160;

	public const byte SwitchConfig = 162;

	public const byte NRFLossCount = 65;

	public const byte BurstCmdID = 96;

	public const byte SubCmdSETID = 1;

	public const byte SubCmdGETID = 2;

	public const byte SubFunc_PrefixId = 80;

	public const byte SubFunc_SaveFlashConfig = 3;

	public const byte SubFunc_ReadRandomId = 2;

	public const byte SubFunc_ReadAllRandomId = 4;

	public const byte SubFunc_SwitchConfig = 5;

	public const byte SubFunc_SwitchMapConfig = 6;

	public const byte SubFunc_MapConfigStatus = 7;

	public const byte SubFunc_TriggerEliminateJitter = 8;

	public const byte SubFunc_JoyAutoCorrect = 9;

	public const byte SubFunc_JSReturnRate = 10;

	public const byte SubFunc_JSResolution = 11;

	public const byte SubFunc_JSLineCenterSens = 13;

	public const byte SubFunc_JSRebounceAlgorithm = 14;

	public const byte SubFunc_JSRoundType = 16;

	static CommandDic()
	{
		SubCmdId = new Dictionary<string, byte>();
		SubCmdId.Add("GamePadInfo", 16);
		SubCmdId.Add("DongleInfo", 17);
		SubCmdId.Add("MotorShock", 18);
		SubCmdId.Add("LedTest", 19);
		SubCmdId.Add("JoystickReset", 20);
		SubCmdId.Add("LightTest", 21);
		SubCmdId.Add("Dormancy", 22);
		SubCmdId.Add("SwitchDinput", 23);
		SubCmdId.Add("IsUseKeyMap", 24);
		SubCmdId.Add("CloseMacro", 25);
		SubCmdId.Add("GetCurConfigId", 32);
		SubCmdId.Add("ReadConfigId", 33);
		SubCmdId.Add("KeyMapCfgReport", 34);
		SubCmdId.Add("StartFLashDataKMPC", 35);
		SubCmdId.Add("WriteDataKMPC", 36);
		SubCmdId.Add("StartKMPC", 37);
		SubCmdId.Add("K1CmdID", 48);
		SubCmdId.Add("Dongle571UpgradeCmd", 64);
		SubCmdId.Add("Dongle571UpgradeCmdSubCmd", 1);
		SubCmdId.Add("WCH582UpgradeCmd", 48);
		SubCmdId.Add("WCH582UpgradeCmdSubCmd", 11);
		SubCmdId.Add("WCH547UpgradeCmd", 48);
		SubCmdId.Add("WCH547UpgradeCmdSubCmd", 12);
		SubCmdId.Add("KZGPUpgradeCmd", 48);
		SubCmdId.Add("KZGPUpgradeCmdSubCmd", 11);
		SubCmdId.Add("TriggerMotorVib", 80);
		SubCmdId.Add("SpecifyConfigId", 160);
		SubCmdId.Add("ReadLedConfigById", 38);
		SubCmdId.Add("WriteLed", 41);
		SubCmdId.Add("StartWriteLed", 42);
		SubCmdId.Add("UUID", 160);
		SubCmdId.Add("SwitchConfig", 162);
		SubCmdId.Add("NRFLossCount", 65);
		SubCmdId.Add("BurstCmdID", 96);
		SubCmdId.Add("SubCmdSETID", 1);
		SubCmdId.Add("SubCmdGETID", 2);
		SubCmdId.Add("StartFLashLEDDataKMPC", 40);
	}
}

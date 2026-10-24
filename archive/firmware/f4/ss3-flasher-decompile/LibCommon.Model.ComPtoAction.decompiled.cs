using System.Collections.Generic;

namespace LibCommon.Model;

public static class ComPtoAction
{
	public static Dictionary<int, string> Action = new Dictionary<int, string>
	{
		{ 0, "UpdateGamepadInfo" },
		{ 1, "GamepadConnect" },
		{ 2, "GamepadUnConnect" },
		{ 3, "UpdateGamepadInfoNotify" },
		{ 4, "GetGamepadConfigInfo" },
		{ 5, "UpdateGamepadConfigInfo" },
		{ 6, "ApplyGamepadConfigInfo" },
		{ 7, "ApplyGamepadConfigCB" },
		{ 8, "ApplyKbMoConfigInfo" },
		{ 9, "ApplyKbMoConfigInfoCB" },
		{ 10, "ApplyScreenPic" },
		{ 11, "ApplyScreenPicCB" },
		{ 12, "GetScreenInfo" },
		{ 13, "GetScreenInfoCB" },
		{ 14, "ApplyScreenInfo" },
		{ 15, "ApplyScreenInfoCB" },
		{ 16, "ApplyScreenSinglePicSuccessCB" },
		{ 17, "ListenOperationData" },
		{ 18, "ListenOperationDataCB" },
		{ 19, "StopOperationData" },
		{ 20, "ListenOperationMappingData" },
		{ 21, "ListenOperationMappingDataCB" },
		{ 22, "StopOperationMappingData" },
		{ 23, "ApplyGamepadTriggerData" },
		{ 24, "GetGamepadInfo" },
		{ 25, "GetGamepadInfoCB" },
		{ 26, "SwitchMode" },
		{ 27, "SwitchXInputMode" },
		{ 28, "SwitchDInputMode" },
		{ 40, "ApplySleepTime" },
		{ 31, "GetUUID" },
		{ 32, "GetUUIDCB" },
		{ 33, "GetSleepTime" },
		{ 34, "GetSleepTimeCB" },
		{ 37, "SetSwitchConfig" },
		{ 38, "GetSwitchConfig" },
		{ 39, "GetSwitchConfigCB" },
		{ 48, "UpdateGamepadId" },
		{ 49, "UpdateGamepadIdRead" },
		{ 50, "MenuFuncCB" },
		{ 51, "NRFLossCount" },
		{ 52, "NRFLossCountCB" },
		{ 53, "ServiceLog" },
		{ 54, "StopCheck" },
		{ 57, "UnInstallDriverService" },
		{ 58, "SwitchKeyMouService" },
		{ 59, "UpgradeCmd" },
		{ 61, "GameModServiceNotify" },
		{ 62, "ApplyModConfig" },
		{ 64, "GetGamepadConfigId" },
		{ 65, "GetGamepadConfigIdCB" },
		{ 66, "GetKeyBurst" },
		{ 67, "GetKeyBurstCB" },
		{ 68, "SetKeyBurst" },
		{ 69, "SetKeyBurstCB" },
		{ 70, "ApplyTempConfig" },
		{ 71, "ApplyTempConfigCB" },
		{ 72, "ApplyTempLEDConfig" },
		{ 73, "ApplyTempLEDConfigCB" },
		{ 74, "SaveFlashConfig" },
		{ 75, "SaveFlashConfigCB" },
		{ 76, "TestMotor" },
		{ 77, "ReadConfigRandom" },
		{ 78, "ReadConfigRandomCB" },
		{ 79, "ReadAllConfigRandom" },
		{ 80, "ReadAllConfigRandomCB" },
		{ 81, "SwichConfigID" },
		{ 82, "SwichConfigIDCB" },
		{ 86, "ChangeIPDeviceID" },
		{ 87, "ApplyDefault" },
		{ 90, "BLEDeviceConnect" },
		{ 91, "BLEDeviceUnConnect" }
	};

	public const string UpdateGamepadInfo = "UpdateGamePadInfo";

	public const string GamepadConnect = "GamePadConnect";

	public const string GamepadUnConnect = "GamePadUnConnect";

	public const string GetGamepadConfigInfo = "GetConfigInfo";

	public const string UpdateGamepadConfigInfo = "UpdateGamepadConfigInfo";

	public const string ApplyGamepadConfigInfo = "ApplyGamepadConfigInfo";

	public const string ApplyGamepadConfigCB = "ApplyGamepadConfigCB";

	public const string ApplyScreenPic = "ApplyScreenPic";

	public const string ApplyScreenPicCB = "ApplyScreenPicCB";

	public const string GetScreenInfo = "GetScreenInfo";

	public const string GetScreenInfoCB = "GetScreenInfoCB";

	public const string ApplyScreenInfo = "ApplyScreenInfo";

	public const string ApplyScreenInfoCB = "ApplyScreenInfoCB";

	public const string UpdateGamepadId = "UpdateGamepadId";
}

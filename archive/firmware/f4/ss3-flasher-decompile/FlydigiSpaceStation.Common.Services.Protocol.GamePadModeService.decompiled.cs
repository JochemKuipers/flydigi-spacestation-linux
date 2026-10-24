using FlydigiSpaceStation.Common.DataManager;
using LibCommon.Model;
using LibCommon.Model.ProtocolModel;
using Newtonsoft.Json;

namespace FlydigiSpaceStation.Common.Services.Protocol;

public class GamePadModeService : BaseProtocolService
{
	public static void SwitchMode(string mode)
	{
		GamepadModeReport gamepadModeReport = new GamepadModeReport();
		gamepadModeReport.mode = mode;
		gamepadModeReport.ReportId = UniqueData.ReportId;
		string objStr = JsonConvert.SerializeObject(gamepadModeReport);
		if (mode == "DInput")
		{
			BaseProtocolService.PostMessage(FDGComPtoAction.SwitchDInputMode, objStr);
		}
		else if (mode == "XInput")
		{
			BaseProtocolService.PostMessage(FDGComPtoAction.SwitchXInputMode, objStr);
		}
		else if (mode.ToLower() == "xinput_ota")
		{
			BaseProtocolService.PostMessage(FDGComPtoAction.SwitchMode, objStr);
		}
		else if (mode.ToLower() == "dinput_ota")
		{
			BaseProtocolService.PostMessage(FDGComPtoAction.SwitchMode, objStr);
		}
	}
}

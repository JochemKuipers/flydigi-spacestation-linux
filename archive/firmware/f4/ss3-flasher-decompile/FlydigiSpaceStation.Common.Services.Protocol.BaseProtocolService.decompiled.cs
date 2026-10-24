using FlydigiSpaceStation.Common.DataManager;
using LibCommon.Model;
using Newtonsoft.Json;

namespace FlydigiSpaceStation.Common.Services.Protocol;

public class BaseProtocolService
{
	public static void PostMessage(FDGComPtoAction actionNew, string objStr)
	{
		FDGComProtocolData fDGComProtocolData = new FDGComProtocolData();
		fDGComProtocolData.ActionNew = actionNew;
		if (ComPtoAction.Action.ContainsKey((int)actionNew))
		{
			fDGComProtocolData.Action = ComPtoAction.Action[(int)actionNew];
		}
		else
		{
			fDGComProtocolData.Action = "Undefined";
		}
		fDGComProtocolData.ActionData = objStr;
		string msg = JsonConvert.SerializeObject(fDGComProtocolData);
		SendEventMessage(msg);
	}

	public static void PostMessage(int actionEnum, string objStr)
	{
		FDGComProtocolData fDGComProtocolData = new FDGComProtocolData();
		fDGComProtocolData.ActionNew = (FDGComPtoAction)actionEnum;
		if (ComPtoAction.Action.ContainsKey(actionEnum))
		{
			fDGComProtocolData.Action = ComPtoAction.Action[actionEnum];
		}
		else
		{
			fDGComProtocolData.Action = "Undefined";
		}
		fDGComProtocolData.ActionData = objStr;
		string msg = JsonConvert.SerializeObject(fDGComProtocolData);
		SendEventMessage(msg);
	}

	public static void PostMessage(FDGComPtoAction actionEnum, FDGComPtoActionParams actionParam, string objStr)
	{
		FDGComProtocolData fDGComProtocolData = new FDGComProtocolData();
		fDGComProtocolData.ActionNew = actionEnum;
		fDGComProtocolData.ActionParams = actionParam;
		if (ComPtoAction.Action.ContainsKey((int)actionEnum))
		{
			fDGComProtocolData.Action = ComPtoAction.Action[(int)actionEnum];
		}
		else
		{
			fDGComProtocolData.Action = "Undefined";
		}
		fDGComProtocolData.ActionData = objStr;
		SendEventMessage(JsonConvert.SerializeObject(fDGComProtocolData));
	}

	private static void SendEventMessage(string msg)
	{
		UniqueData.tcpClient?.SendEventMsg(msg);
	}
}

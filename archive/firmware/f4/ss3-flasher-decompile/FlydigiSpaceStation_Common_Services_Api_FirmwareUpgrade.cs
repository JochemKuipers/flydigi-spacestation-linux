using System.Collections.Generic;
using System.Reflection;
using System.Text;

namespace FlydigiSpaceStation.Common.Services.Api;

public class FirmwareUpgrade
{
	public string firmName;

	public string cpuType;

	public string lang;

	public string appVersion;

	public string reqUrl;

	public string apiHost;

	public Dictionary<string, string> parmasDic;

	public FirmwareUpgrade(string _apiHost, string _firmName, string _cpuType, string currentVersion)
	{
		firmName = _firmName;
		cpuType = _cpuType;
		lang = App.lang;
		appVersion = Assembly.GetExecutingAssembly().GetName().Version.ToString();
		parmasDic = new Dictionary<string, string>();
		parmasDic.Add("type", firmName);
		parmasDic.Add("cpuName", cpuType);
		parmasDic.Add("lang", lang);
		parmasDic.Add("appVersion", appVersion);
		parmasDic.Add("currentVersion", currentVersion);
		apiHost = _apiHost;
		reqUrl = GetUrl(apiHost, parmasDic);
	}

	public string getReqUrl()
	{
		return reqUrl;
	}

	public static string GetUrl(string url, Dictionary<string, string> dic)
	{
		StringBuilder stringBuilder = new StringBuilder();
		stringBuilder.Append(url);
		if (dic.Count > 0)
		{
			stringBuilder.Append("?");
			int num = 0;
			foreach (KeyValuePair<string, string> item in dic)
			{
				if (num > 0)
				{
					stringBuilder.Append("&");
				}
				stringBuilder.AppendFormat("{0}={1}", item.Key, item.Value);
				num++;
			}
		}
		return stringBuilder.ToString();
	}
}

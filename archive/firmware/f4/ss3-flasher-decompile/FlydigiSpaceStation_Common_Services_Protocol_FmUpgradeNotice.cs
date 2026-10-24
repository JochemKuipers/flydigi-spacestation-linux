using LibCommon.Model;

namespace FlydigiSpaceStation.Common.Services.Protocol;

public class FmUpgradeNotice : BaseProtocolService
{
	public static void NoticeFMUpgrade(bool isFmUpgrade)
	{
		BaseProtocolService.PostMessage(FDGComPtoAction.NoticeFMUpgrade, isFmUpgrade.ToString());
	}
}

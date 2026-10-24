using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using FlydigiSpaceStation.Common.Utils;
using LibCommon.Model;
using LibCommon.Utils;
using Newtonsoft.Json;

namespace FlydigiSpaceStation.Common.FmUpgrade;

internal class WchIspHelper
{
	private delegate bool WriteFlashProgramDelegate(uint index, IntPtr pDataBuf, uint uOutFileLen);

	public static bool downLoadStatus;

	public static bool connectStatus;

	public static bool AfxIspIsRunning = false;

	public static bool AfxIspDevIsChanged = false;

	public static bool AfxAutoDnAfterPlug = true;

	public static bool IsDownloading;

	public static bool IsDeviceChanged;

	public static bool IsStartDownload;

	public const int MAX_ISPDEV_NUM = 16;

	public static CH55xIspOptionS IspOption = default;

	public static Isp55xDevInforS[] oAfxDnDev = new Isp55xDevInforS[16];

	public static Isp55xDevInforS[] mIsp55xDevInforS = new Isp55xDevInforS[16];

	public static Isp55xDevInforS curIsp55xDevInfor = default;

	public static byte IspMcuType = 130;

	public static bool IsClearDataFlash = false;

	public static byte BootPinNum = 0;

	public static byte IspChipSeries = 6;

	public static uint LastSerPortSel = 0u;

	public static uint AfxDnDevCnt = 0u;

	public static uint AfxIspDnSuccCnt = 0u;

	public static uint AfxIspDnErrCnt = 0u;

	public static bool StopProcThread = false;

	public static void Initialize()
	{
		FLog.d("Isp55xDevInforS size:" + (uint)Marshal.SizeOf<Isp55xDevInforS>(default));
		FLog.d("CHIP_INFOEX size:" + (uint)Marshal.SizeOf<CHIP_INFOEX>(default));
		FLog.d("CH55xIspOptionS size:" + (uint)Marshal.SizeOf<CH55xIspOptionS>(default));
		if (!CH55x_SetIspOption())
		{
			FLog.d("CH55x_SetIspOption init failed");
		}
	}

	public static void StartEnumIspDeviceProcThread()
	{
		new Thread((object? o) =>
		{
			EnumIspDeviceProc();
		}).Start();
	}

	public static FDGDeviceFirmware EnumIspDeviceProc()
	{
		IntPtr intPtr;
		while (true)
		{
			Thread.Sleep(1000);
			FLog.d("EnumIspDeviceProc");
			if (connectStatus)
			{
				return null;
			}
			if (StopProcThread)
			{
				return null;
			}
			if (IsDownloading)
			{
				FLog.d("IsDownloading:" + IsDownloading);
				return null;
			}
			if (IsStartDownload)
			{
				FLog.d("IsStartDownload:" + IsStartDownload);
				return null;
			}
			if (!CH55x_SetIspOption())
			{
				FLog.d("CH55x_SetIspOption init failed");
				return null;
			}
			uint num = 0u;
			byte[] array = new byte[512];
			byte[] array2 = new byte[2];
			byte[] array3 = new byte[2];
			bool IsPreBTV = false;
			IntPtr[] source = new IntPtr[1] { Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Isp55xDevInforS))) };
			intPtr = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Isp55xDevInforS)));
			Marshal.Copy(source, 0, intPtr, 1);
			AfxDnDevCnt = WCH55xISPDLL.WCH55x_EnumDevices(intPtr, 10, ref array3[0], ref array2[0], ref IsPreBTV);
			FLog.d("AfxDnDevCnt:" + AfxDnDevCnt);
			if (AfxDnDevCnt == 0)
			{
				Marshal.FreeHGlobal(intPtr);
				connectStatus = false;
				FDGDeviceFirmware fDGDeviceFirmware = new FDGDeviceFirmware();
				fDGDeviceFirmware.ConnectStatusString = "设备未连接";
				fDGDeviceFirmware.IsConnect = false;
			}
			else if (AfxDnDevCnt != 0)
			{
				FLog.d("found device");
				curIsp55xDevInfor = (Isp55xDevInforS)Marshal.PtrToStructure(intPtr, typeof(Isp55xDevInforS));
				if (curIsp55xDevInfor.Index <= 20)
				{
					connectStatus = true;
				}
				if (connectStatus)
				{
					break;
				}
			}
		}
		FDGDeviceFirmware fDGDeviceFirmware2 = new FDGDeviceFirmware();
		fDGDeviceFirmware2.ConnectStatusString = "连接成功";
		fDGDeviceFirmware2.IsConnect = true;
		Marshal.FreeHGlobal(intPtr);
		return fDGDeviceFirmware2;
	}

	public static int ISPFlashDnThread_CH55xUSB(string fullPath)
	{
		IsDownloading = true;
		IsStartDownload = true;
		AfxIspIsRunning = true;
		int result;
		if (!CH55x_SetIspOption())
		{
			result = -1;
			FLog.d("CH55x_SetIspOption error");
			return result;
		}
		uint num = 0u;
		if (num >= AfxDnDevCnt)
		{
			return -2;
		}
		if (IspOption.IspMcuSeries == 4 && !WCH55xISPDLL.WCH55x_IspRemoveProtect(num))
		{
			result = -2;
			FLog.d("设备解保护失败!");
			return result;
		}
		Isp55xDevInforS isp55xDevInforS = curIsp55xDevInfor;
		uint oWriteLen = 1048576u;
		if (IspOption.IsClearDataFlash)
		{
			if (!WCH55xISPDLL.WCH55x_WriteDataFlash(isp55xDevInforS.Index, 0u, ref oWriteLen, "CLEAR", bIsErase: true))
			{
				FLog.d("清空DataFlash失败...");
				return -4;
			}
			FLog.d("清空DataFlash成功...");
		}
		FileInfo fileInfo = new FileInfo(fullPath);
		uint userFileDataLen = (uint)fileInfo.Length;
		string s = File.ReadAllText(fullPath);
		FLog.d("fullPath:" + fullPath);
		IntPtr userFileDataBuf = Marshal.StringToHGlobalAnsi(s);
		bool flag = false;
		try
		{
			FLog.d("WCH55x_FlashProgramB IspOption:" + JsonConvert.SerializeObject(IspOption));
			flag = WCH55xISPDLL.WCH55x_FlashProgramB(isp55xDevInforS.Index, userFileDataBuf, userFileDataLen, 0, "", 0u, 0);
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			result = -6;
			FLog.d("download error:" + result + " message:" + ex.Message + " StackTrace:" + ex.StackTrace);
			return result;
		}
		finally
		{
		}
		if (!flag)
		{
			FLog.d("download error");
			AfxIspDnErrCnt++;
			connectStatus = false;
			result = -5;
		}
		else
		{
			result = 1;
			FLog.d("download success");
			AfxIspDnSuccCnt++;
		}
		IsDownloading = false;
		return result;
	}

	private static bool WriteFlashProgram(uint index, IntPtr pDataBuf, uint uOutFileLen)
	{
		FLog.d("WriteFlashProgram index:" + index + " pDataBuf:" + pDataBuf + " uOutFileLen:" + uOutFileLen);
		if (index > 20)
		{
			return false;
		}
		return WCH55xISPDLL.WCH55x_FlashProgramB(index, pDataBuf, uOutFileLen, 0, "", 0u, 0);
	}

	public static bool CH55x_SetIspOption()
	{
		byte[] array = new byte[64];
		byte[] array2 = new byte[260];
		bool flag = false;
		IspOption.IspMcuType = IspMcuType;
		IspOption.IspMcuSeries = IspChipSeries;
		IspOption.IspInterface = 0u;
		IspOption.IsMcuResetAfterIsp = true;
		IspOption.IsEnableLongRest = false;
		IspOption.IsEnableResetPin = false;
		IspOption.IsXtOscStrong = false;
		IspOption.IsEnableP0PullUp = true;
		IspOption.IsEnableIAP = false;
		IspOption.IAPStartAddr = 0u;
		IspOption.IsEnableUsbPnpNotify = false;
		IspOption.BootPinNum = BootPinNum;
		IspOption.IsNoKeyDnAtSer = false;
		IspOption.IsClearDataFlash = IsClearDataFlash;
		IspOption.IsBootLoader = true;
		IspOption.IsCodeProtect = true;
		IspOption.IsEnableCfgBuf64K = false;
		IspOption.EnableIce = false;
		IspOption.IsSetDevIP = false;
		IspOption.LV_RST_VOL = 0;
		IspOption.IsUsbdMode = false;
		IspOption.IsStopRst = false;
		IspOption.IsStandbyRst = false;
		IspOption.IsUsbdPu = false;
		IspOption.IsIwdgSw = false;
		IspOption.IsEraseAllCFlash = true;
		IspOption.Baud = new byte[4];
		IspOption.Baud[0] = 64;
		IspOption.Baud[1] = 66;
		IspOption.Baud[2] = 15;
		IspOption.Baud[3] = 0;
		if (IspOption.IspMcuSeries == 0 && IspOption.IspMcuType <= 3)
		{
			IspOption.IsXtOscStrong = false;
			IspOption.IsEnableP0PullUp = false;
			IspOption.IsFirstRunIAP = false;
			IspOption.IsEnableIAP = false;
		}
		if (IspOption.IspInterface == 1)
		{
			IspOption.IsEnableUsbPnpNotify = false;
		}
		IntPtr intPtr = Marshal.AllocHGlobal(Marshal.SizeOf(IspOption));
		Marshal.StructureToPtr(IspOption, intPtr, fDeleteOld: false);
		try
		{
			flag = !WCH55xISPDLL.WCH55x_SetIspOptionPtr(intPtr) || true;
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			return false;
		}
		return flag;
	}

	public static bool setIspMcuType(byte mcuType)
	{
		IspMcuType = mcuType;
		return CH55x_SetIspOption();
	}

	public static bool setIsClearDataFlash(bool isClearDataFlash)
	{
		IsClearDataFlash = isClearDataFlash;
		return CH55x_SetIspOption();
	}

	public static bool setBootPinNum(byte bootPinNum)
	{
		BootPinNum = bootPinNum;
		return CH55x_SetIspOption();
	}

	public static bool setIspChipSeries(byte ChipSeries)
	{
		IspChipSeries = ChipSeries;
		return CH55x_SetIspOption();
	}

	public static void RemoveListen()
	{
		IsStartDownload = true;
		StopProcThread = true;
	}

	public static void AddListen()
	{
		IsStartDownload = false;
		IsDownloading = false;
		connectStatus = false;
		StopProcThread = false;
	}
}

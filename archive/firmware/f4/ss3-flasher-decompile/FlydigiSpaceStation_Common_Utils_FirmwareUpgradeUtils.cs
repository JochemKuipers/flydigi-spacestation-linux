using System;
using System.IO;
using System.Text;
using System.Windows;
using LibCommon.Utils;

namespace FlydigiSpaceStation.Common.Utils;

internal static class FirmwareUpgradeUtils
{
	public static bool Debug_enable = true;

	public static string AESkey;

	public static void debug_output(string failReason)
	{
		//IL_0023: Unknown result type (might be due to invalid IL or missing references)
		if (Debug_enable)
		{
			MessageBox.Show("您设置的参数错误,或者您的操作有误，请检查，失败原因如下:\r\n" + failReason, "错误警告", (MessageBoxButton)0, (MessageBoxImage)16);
		}
	}

	public static string[] readFile(string FilePath)
	{
		try
		{
			if (File.Exists(FilePath))
			{
				return File.ReadAllLines(FilePath, Encoding.Default);
			}
			return null;
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			debug_output(ex.ToString());
			return null;
		}
	}

	public static string openFile(string FilePath)
	{
		try
		{
			if (File.Exists(FilePath))
			{
				File.OpenRead(FilePath);
				return "ok";
			}
			return null;
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			debug_output(ex.ToString());
			return null;
		}
	}

	public static bool writeFile(string FilePath, string write_str)
	{
		try
		{
			if (File.Exists(FilePath))
			{
				File.Delete(FilePath);
			}
			FileStream fileStream = new FileStream(FilePath, FileMode.CreateNew, FileAccess.Write);
			StreamWriter streamWriter = new StreamWriter(fileStream, Encoding.Default);
			streamWriter.Write(write_str);
			streamWriter.Close();
			fileStream.Close();
			return true;
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			return false;
		}
	}

	public static bool ReadBinFile(string FilePathAndName, ref byte[] backBytes, ref uint bin_size)
	{
		//IL_007f: Unknown result type (might be due to invalid IL or missing references)
		//IL_004d: Unknown result type (might be due to invalid IL or missing references)
		try
		{
			bin_size = 0u;
			if (File.Exists(FilePathAndName))
			{
				FileStream fileStream = new FileStream(FilePathAndName, FileMode.Open, FileAccess.Read);
				BinaryReader binaryReader = new BinaryReader(fileStream);
				backBytes = binaryReader.ReadBytes((int)(bin_size = (uint)fileStream.Length));
				binaryReader.Close();
				fileStream.Close();
				return true;
			}
			MessageBox.Show("文件路径不对或者文件不存在");
			return false;
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			bin_size = 0u;
			MessageBox.Show("读文件失败！原因：" + ex.ToString());
			return false;
		}
	}

	public static string WriteBinFlie(string FilePathAndName, byte[] srcBytes, int len)
	{
		FileStream fileStream = null;
		BinaryWriter binaryWriter = null;
		try
		{
			if (File.Exists(FilePathAndName))
			{
				File.Delete(FilePathAndName);
			}
			fileStream = new FileStream(FilePathAndName, FileMode.Create, FileAccess.Write);
			binaryWriter = new BinaryWriter(fileStream);
			for (uint num = 0u; num < len; num++)
			{
				binaryWriter.Write(srcBytes[num]);
			}
			binaryWriter.Close();
			fileStream.Close();
			binaryWriter = null;
			fileStream = null;
			return null;
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			return ex.Message + "\r\n在写入文件的过程中，发生了异常！";
		}
	}

	public static ushort crc16(byte[] pD, int len)
	{
		ushort[] array = new ushort[2] { 0, 40961 };
		ushort num = ushort.MaxValue;
		int num2 = 0;
		for (int num3 = len; num3 > 0; num3--)
		{
			ushort num4 = pD[num2];
			num2++;
			for (int i = 0; i < 8; i++)
			{
				num = (ushort)((num >> 1) ^ array[(num ^ num4) & 1]);
				num4 >>= 1;
			}
		}
		return num;
	}

	public static byte[] HexStringToToHexByte(string hexString)
	{
		hexString = hexString.Replace(" ", "");
		if (hexString.Length % 2 != 0)
		{
			hexString += " ";
		}
		byte[] array = new byte[hexString.Length / 2];
		for (int i = 0; i < array.Length; i++)
		{
			array[i] = Convert.ToByte(hexString.Substring(i * 2, 2), 16);
		}
		return array;
	}

	public static string HexByteToHexString(byte[] hexBytes, int length, string space)
	{
		string text = "";
		for (int i = 0; i < length; i++)
		{
			text = text + hexBytes[i].ToString("X2") + space;
		}
		return text;
	}

	public static string HexByteToHexString(byte[] hexBytes)
	{
		string text = "";
		for (int i = 0; i < hexBytes.Length; i++)
		{
			text = text + hexBytes[i].ToString("X2") + ":";
		}
		return text;
	}

	public static void math_cpy(byte[] s_buf, int s_position, ref byte[] r_buf, int r_positon, int length)
	{
		for (int i = 0; i < length; i++)
		{
			r_buf[r_positon + i] = s_buf[s_position + i];
		}
	}
}

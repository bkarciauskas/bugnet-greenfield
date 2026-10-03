using System.Security.Cryptography;
using System.Text;

namespace BugNet.Data.Persistence;

internal static class MembershipPassword
{
    public static string CreateSalt()
    {
        var salt = new byte[16];
        RandomNumberGenerator.Fill(salt);
        return Convert.ToBase64String(salt);
    }

    public static string HashForStorage(string password, string salt)
    {
        return HashHmacSha256(password, salt);
    }

    public static bool Matches(string password, string salt, string stored, int format)
    {
        if (format == 0)
        {
            return string.Equals(password, stored, StringComparison.Ordinal);
        }

        if (format != 1)
        {
            return false;
        }

        var hmac = HashHmacSha256(password, salt);
        if (FixedEquals(hmac, stored))
        {
            return true;
        }

        return FixedEquals(HashSha1(password, salt), stored);
    }

    private static bool FixedEquals(string left, string right)
    {
        var a = Encoding.ASCII.GetBytes(left);
        var b = Encoding.ASCII.GetBytes(right);
        return a.Length == b.Length && CryptographicOperations.FixedTimeEquals(a, b);
    }

    private static string HashHmacSha256(string password, string salt)
    {
        var saltBytes = Convert.FromBase64String(salt);
        var data = Encoding.Unicode.GetBytes(password);
        using var hmac = new HMACSHA256();
        hmac.Key = FitKey(saltBytes, hmac.Key.Length);
        return Convert.ToBase64String(hmac.ComputeHash(data));
    }

    [System.Diagnostics.CodeAnalysis.SuppressMessage("Security", "CA5350", Justification = "Existing membership rows were stored with SHA1.")]
    private static string HashSha1(string password, string salt)
    {
        var saltBytes = Convert.FromBase64String(salt);
        var data = Encoding.Unicode.GetBytes(password);
        var all = new byte[saltBytes.Length + data.Length];
        Buffer.BlockCopy(saltBytes, 0, all, 0, saltBytes.Length);
        Buffer.BlockCopy(data, 0, all, saltBytes.Length, data.Length);
        return Convert.ToBase64String(SHA1.HashData(all));
    }

    private static byte[] FitKey(byte[] salt, int keyLength)
    {
        var key = new byte[keyLength];
        if (salt.Length == keyLength)
        {
            return salt;
        }

        if (salt.Length > keyLength)
        {
            Buffer.BlockCopy(salt, 0, key, 0, keyLength);
            return key;
        }

        var offset = 0;
        while (offset < keyLength)
        {
            var length = Math.Min(salt.Length, keyLength - offset);
            Buffer.BlockCopy(salt, 0, key, offset, length);
            offset += length;
        }

        return key;
    }
}

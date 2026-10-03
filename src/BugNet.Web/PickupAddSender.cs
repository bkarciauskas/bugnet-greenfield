using System.Text;
using BugNet.Core;

namespace BugNet.Web;

public sealed class PickupAddSender : IAddSender
{
    private readonly string _directory;

    public PickupAddSender(string directory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(directory);
        _directory = directory;
        Directory.CreateDirectory(directory);
    }

    public StartedSend Start(AddNotification notification)
    {
        ArgumentNullException.ThrowIfNull(notification);
        var completion = Task.Run(() => Write(notification));
        return new StartedSend(completion);
    }

    private void Write(AddNotification notification)
    {
        foreach (var copy in notification.Copies)
        {
            var message = Build(notification, copy);
            var path = Path.Combine(_directory, Guid.NewGuid().ToString("N") + ".eml");
            File.WriteAllText(path, message, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        }
    }

    private static string Build(AddNotification notification, NotificationCopy copy)
    {
        var body = Convert.ToBase64String(Encoding.UTF8.GetBytes(copy.Body), Base64FormattingOptions.InsertLineBreaks);
        var type = notification.IsBodyHtml ? "text/html" : "text/plain";
        return string.Concat(
            "From: ",
            FormatFrom(notification.FromDisplayName, notification.FromAddress),
            "\r\nTo: ",
            copy.Address,
            "\r\nSubject: ",
            EncodeHeader(copy.Subject),
            "\r\nMIME-Version: 1.0\r\nContent-Type: ",
            type,
            "; charset=utf-8\r\nContent-Transfer-Encoding: base64\r\n\r\n",
            body,
            "\r\n");
    }

    private static string FormatFrom(string displayName, string address)
    {
        var name = displayName.All(static c => c < 128)
            ? "\"" + displayName.Replace("\\", "\\\\", StringComparison.Ordinal).Replace("\"", "\\\"", StringComparison.Ordinal) + "\""
            : EncodeHeader(displayName);
        return name + " <" + address + ">";
    }

    private static string EncodeHeader(string value)
    {
        if (value.All(static c => c < 128))
        {
            return value;
        }

        return "=?utf-8?B?" + Convert.ToBase64String(Encoding.UTF8.GetBytes(value)) + "?=";
    }
}

using System.Globalization;
using System.Text;
using System.Xml;
using System.Xml.Xsl;

namespace BugNet.Core;

public static class AddNotificationText
{
    private static readonly Dictionary<string, string> Subjects = new(StringComparer.Ordinal)
    {
        [""] = "Issue {0} has been added to a project you are monitoring.",
        ["de-DE"] = "Aufgabe {0} wurde zu einem von Ihnen überwachten Projekt hinzugefügt.",
        ["es-ES"] = "El caso {0} se ha añadido a un proyecto que está monitorizando.",
        ["fr-CA"] = "Anomalie {0} a été ajoutée à un projet que vous surveillez.",
        ["it-IT"] = "La segnalazione {0} è stata aggiunta al progetto che stai osservando.",
        ["nl-NL"] = "Punt {0} is toegevoegd aan een project wat u volgt.",
        ["ro-RO"] = "Problema {0} a fost adaugata la proiectul pe care-l monitorizati.",
        ["ru-RU"] = "Задание {0} было добавлено в наблюдаемый Вами проект.",
        ["zh-CN"] = "你关注的项目添加了一个新问题 {0}",
    };

    private static readonly XsltHelpers Helpers = new();
    private static readonly Dictionary<string, XslCompiledTransform> Transforms = new(StringComparer.Ordinal);

    public static string FromAddress(string hostEmail, bool allowReplyTo, int issueId)
    {
        ArgumentNullException.ThrowIfNull(hostEmail);
        if (!allowReplyTo)
        {
            return hostEmail;
        }

        var at = hostEmail.IndexOf('@', StringComparison.Ordinal);
        if (at < 0)
        {
            return hostEmail;
        }

        return string.Concat(
            hostEmail.AsSpan(0, at),
            "+iid-",
            issueId.ToString(CultureInfo.InvariantCulture),
            hostEmail.AsSpan(at));
    }

    public static AddNotification Build(CreateIssue command, SavedIssue saved, HostMailSettings settings)
    {
        ArgumentNullException.ThrowIfNull(command);
        ArgumentNullException.ThrowIfNull(saved);
        ArgumentNullException.ThrowIfNull(settings);

        var html = string.Equals(settings.EmailFormat, "2", StringComparison.Ordinal);
        if (!html && !string.Equals(settings.EmailFormat, "1", StringComparison.Ordinal))
        {
            throw new InvalidOperationException("unread mail format setting");
        }

        var copies = new List<NotificationCopy>();
        foreach (var subscriber in DistinctRecipients(saved.Subscribers))
        {
            var culture = MailCulture(subscriber, settings);
            var subject = Subject(culture, IssueCreation.IssueKey(saved.ProjectCode, saved.Id));
            var body = Render(command, saved, settings, culture, html);
            copies.Add(new NotificationCopy(subscriber.Email, culture, subject, body));
        }

        return new AddNotification(
            settings.ApplicationTitle,
            FromAddress(settings.HostEmailAddress, settings.AllowReplyTo, saved.Id),
            html,
            copies);
    }

    public static string Subject(string? culture, string issueKey)
    {
        var name = SubjectCulture(culture);
        if (!Subjects.TryGetValue(name, out var pattern))
        {
            throw new InvalidOperationException("no IssueAddedSubject for culture " + (string.IsNullOrEmpty(name) ? "(empty)" : name));
        }

        return string.Format(CultureInfo.InvariantCulture, pattern, issueKey);
    }

    private static IEnumerable<Subscriber> DistinctRecipients(IReadOnlyList<Subscriber> subscribers)
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var subscriber in subscribers.OrderBy(item => item.Email, StringComparer.OrdinalIgnoreCase))
        {
            if (!subscriber.Approved || !subscriber.ReceiveEmailNotifications || string.IsNullOrWhiteSpace(subscriber.Email))
            {
                continue;
            }

            if (seen.Add(subscriber.Email))
            {
                yield return subscriber;
            }
        }
    }

    private static string MailCulture(Subscriber subscriber, HostMailSettings settings)
    {
        if (!string.IsNullOrWhiteSpace(subscriber.PreferredLocale))
        {
            return subscriber.PreferredLocale.Trim();
        }

        return (settings.ApplicationDefaultLanguage ?? string.Empty).Trim();
    }

    private static string SubjectCulture(string? culture)
    {
        var name = (culture ?? string.Empty).Trim();
        if (name is "" or "en" or "en-US")
        {
            return "";
        }

        return name;
    }

    private static string TemplateCulture(string culture)
    {
        var name = SubjectCulture(culture);
        return name is "nl-NL" or "ru-RU" or "ro-RO" ? name : "";
    }

    private static string Render(CreateIssue command, SavedIssue saved, HostMailSettings settings, string culture, bool html)
    {
        var transform = TransformFor(html, TemplateCulture(culture));
        var arguments = new XsltArgumentList();
        arguments.AddExtensionObject("urn:xsl-helpers", Helpers);
        using var source = XmlReader.Create(new StringReader(SourceXml(command, saved, settings)), ReaderSettings());
        using var writer = new StringWriter();
        transform.Transform(source, arguments, writer);
        return writer.ToString();
    }

    private static XslCompiledTransform TransformFor(bool html, string culture)
    {
        var key = (html ? "Html" : "Text") + "|" + culture;
        lock (Transforms)
        {
            if (Transforms.TryGetValue(key, out var cached))
            {
                return cached;
            }

            var suffix = culture.Length == 0 ? "" : "." + culture;
            var name = "BugNet.Core.Templates." + (html ? "Html" : "Text") + ".IssueAdded" + suffix + ".xslt";
            var assembly = typeof(AddNotificationText).Assembly;
            using var stream = assembly.GetManifestResourceStream(name) ?? throw new InvalidOperationException("missing template " + name);
            using var reader = new StreamReader(stream, Encoding.UTF8);
            var stylesheet = reader.ReadToEnd();
            var transform = new XslCompiledTransform();
            using var xml = XmlReader.Create(new StringReader(stylesheet), ReaderSettings());
            transform.Load(xml, new XsltSettings(enableDocumentFunction: false, enableScript: false), new XmlUrlResolver());
            Transforms.Add(key, transform);
            return transform;
        }
    }

    private static XmlReaderSettings ReaderSettings() => new()
    {
        DtdProcessing = DtdProcessing.Prohibit,
        XmlResolver = null,
    };

    private static string SourceXml(CreateIssue command, SavedIssue saved, HostMailSettings settings)
    {
        var builder = new StringBuilder();
        using var writer = XmlWriter.Create(builder, new XmlWriterSettings { OmitXmlDeclaration = true });
        writer.WriteStartElement("root");
        writer.WriteElementString("HostSetting_DefaultUrl", settings.DefaultUrl);
        writer.WriteStartElement("Issue");
        writer.WriteElementString("Id", saved.Id.ToString(CultureInfo.InvariantCulture));
        writer.WriteElementString("Title", command.Title);
        writer.WriteElementString("ProjectName", saved.ProjectName);
        writer.WriteElementString("CreatorDisplayName", saved.CreatorDisplayName);
        writer.WriteElementString("MilestoneName", saved.MilestoneName);
        writer.WriteElementString("CategoryName", saved.CategoryName);
        writer.WriteElementString("PriorityName", saved.PriorityName);
        writer.WriteElementString("IssueTypeName", saved.TypeName);
        writer.WriteElementString("Description", command.Description);
        writer.WriteEndElement();
        writer.WriteEndElement();
        writer.Flush();
        return builder.ToString();
    }
}

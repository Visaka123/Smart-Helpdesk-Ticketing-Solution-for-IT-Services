def map_team(text):

    text = str(text).lower()

    if any(
        x in text
        for x in [
            "vpn",
            "wifi",
            "network",
            "router",
            "internet"
        ]
    ):
        return "Network Team"

    elif any(
        x in text
        for x in [
            "sap",
            "erp"
        ]
    ):
        return "SAP Team"

    elif any(
        x in text
        for x in [
            "mysql",
            "oracle",
            "database",
            "sql"
        ]
    ):
        return "Database Team"

    elif "windows" in text:
        return "Windows Team"

    elif "linux" in text:
        return "Linux Team"

    elif any(
        x in text
        for x in [
            "security",
            "malware",
            "virus",
            "phishing"
        ]
    ):
        return "Security Team"

    elif any(
        x in text
        for x in [
            "payroll",
            "employee",
            "hr"
        ]
    ):
        return "HR Systems Team"

    return "Application Support Team"
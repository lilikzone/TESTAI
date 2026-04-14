"""
AWS Region mapping — city/country names to AWS region codes.
Used to inject context into AI prompts so the model resolves
natural language location references correctly.
"""

# Maps common names (lowercase) → AWS region code
REGION_MAP: dict[str, str] = {
    # Asia Pacific
    "jakarta":        "ap-southeast-3",
    "indonesia":      "ap-southeast-3",
    "singapore":      "ap-southeast-1",
    "sydney":         "ap-southeast-2",
    "australia":      "ap-southeast-2",
    "melbourne":      "ap-southeast-4",
    "tokyo":          "ap-northeast-1",
    "japan":          "ap-northeast-1",
    "osaka":          "ap-northeast-3",
    "seoul":          "ap-northeast-2",
    "korea":          "ap-northeast-2",
    "mumbai":         "ap-south-1",
    "india":          "ap-south-1",
    "hyderabad":      "ap-south-2",
    "hong kong":      "ap-east-1",
    "bangkok":        "ap-southeast-7",
    "malaysia":       "ap-southeast-5",
    "kuala lumpur":   "ap-southeast-5",
    "new zealand":    "ap-southeast-6",
    "auckland":       "ap-southeast-6",

    # Americas
    "virginia":       "us-east-1",
    "n. virginia":    "us-east-1",
    "north virginia": "us-east-1",
    "ohio":           "us-east-2",
    "n. california":  "us-west-1",
    "north california": "us-west-1",
    "oregon":         "us-west-2",
    "canada":         "ca-central-1",
    "montreal":       "ca-central-1",
    "calgary":        "ca-west-1",
    "sao paulo":      "sa-east-1",
    "brazil":         "sa-east-1",

    # Europe
    "ireland":        "eu-west-1",
    "london":         "eu-west-2",
    "uk":             "eu-west-2",
    "paris":          "eu-west-3",
    "france":         "eu-west-3",
    "frankfurt":      "eu-central-1",
    "germany":        "eu-central-1",
    "zurich":         "eu-central-2",
    "switzerland":    "eu-central-2",
    "stockholm":      "eu-north-1",
    "sweden":         "eu-north-1",
    "milan":          "eu-south-1",
    "italy":          "eu-south-1",
    "spain":          "eu-south-2",
    "madrid":         "eu-south-2",

    # Middle East & Africa
    "bahrain":        "me-south-1",
    "uae":            "me-central-1",
    "dubai":          "me-central-1",
    "israel":         "il-central-1",
    "tel aviv":       "il-central-1",
    "cape town":      "af-south-1",
    "africa":         "af-south-1",
    "south africa":   "af-south-1",

    # China
    "beijing":        "cn-north-1",
    "china":          "cn-north-1",
    "ningxia":        "cn-northwest-1",

    # GovCloud
    "us gov east":    "us-gov-east-1",
    "us gov west":    "us-gov-west-1",
}


def build_region_hint() -> str:
    """
    Build a compact region mapping string for injection into AI prompts.
    Groups by continent to keep the prompt concise.
    """
    return (
        "AWS region name mapping (use exact region code in commands):\n"
        "- Jakarta/Indonesia=ap-southeast-3, Singapore=ap-southeast-1, "
        "Sydney/Australia=ap-southeast-2, Tokyo/Japan=ap-northeast-1, "
        "Seoul/Korea=ap-northeast-2, Mumbai/India=ap-south-1, "
        "Hong Kong=ap-east-1, Osaka=ap-northeast-3\n"
        "- Virginia/N.Virginia=us-east-1, Ohio=us-east-2, Oregon=us-west-2, "
        "N.California=us-west-1, Canada/Montreal=ca-central-1, "
        "Sao Paulo/Brazil=sa-east-1\n"
        "- Ireland=eu-west-1, London/UK=eu-west-2, Paris/France=eu-west-3, "
        "Frankfurt/Germany=eu-central-1, Stockholm/Sweden=eu-north-1, "
        "Milan/Italy=eu-south-1, Madrid/Spain=eu-south-2\n"
        "- Bahrain=me-south-1, UAE/Dubai=me-central-1, "
        "Cape Town/Africa=af-south-1\n"
        "- Default region if not specified: ap-southeast-3"
    )


def resolve_region(text: str) -> str | None:
    """
    Try to resolve a city/country name from free text to an AWS region code.
    Returns None if no match found.
    """
    text_lower = text.lower()
    for name, code in REGION_MAP.items():
        if name in text_lower:
            return code
    return None

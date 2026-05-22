"""Pre-seeded common Wikidata properties.

These ship with the code so basic lookups never hit the Wikidata API
(avoiding rate limits).
"""

# Each keyword maps to a list of {id, label, description} dicts.
COMMON_PROPERTIES: dict[str, list[dict[str, str]]] = {
    "instance of": [{"id": "P31", "label": "instance of", "description": "that class of which this subject is a particular example and member"}],
    "subclass of": [{"id": "P279", "label": "subclass of", "description": "all instances of this class are instances of that class"}],
    "part of": [{"id": "P361", "label": "part of", "description": "object of which the subject is a part (if the subject is already part of another distinct object)"}],
    "has part": [{"id": "P527", "label": "has part", "description": "part of this subject (the subject is a whole)"}],
    "country": [{"id": "P17", "label": "country", "description": "sovereign state of this item"}],
    "located in": [{"id": "P131", "label": "located in administrative territorial entity", "description": "the item is located on the territory of the following administrative entity"}, {"id": "P276", "label": "location", "description": "location of the item, physical object or event"}],
    "capital": [{"id": "P36", "label": "capital", "description": "seat of government of a country, province, state, or other administrative territorial entity"}],
    "population": [{"id": "P1082", "label": "population", "description": "number of people inhabiting a particular area"}],
    "area": [{"id": "P2046", "label": "area", "description": "total area of a place, including water"}],
    "official language": [{"id": "P37", "label": "official language", "description": "language designated as official by the subject"}],
    "language": [{"id": "P37", "label": "official language", "description": "language designated as official by the subject"}],
    "head of state": [{"id": "P35", "label": "head of state", "description": "office or officer who is the head of state of a country, e.g. president, monarchy, or similar"}],
    "headquarters": [{"id": "P159", "label": "headquarters location", "description": "city or town where an organization's headquarters is or has been situated"}],
    "founding": [{"id": "P571", "label": "inception", "description": "time when an entity begins to exist; for date of official opening use P1619"}],
    "founding date": [{"id": "P571", "label": "inception", "description": "time when an entity begins to exist; for date of official opening use P1619"}],
    "inception": [{"id": "P571", "label": "inception", "description": "time when an entity begins to exist; for date of official opening use P1619"}],
    "founder": [{"id": "P112", "label": "founder", "description": "founder of an organization, religion, place, or other entity"}],
    "website": [{"id": "P856", "label": "official website", "description": "URL of the official page of an item"}],
    "stock exchange": [{"id": "P414", "label": "stock exchange", "description": "stock exchange where the subject is traded"}],
    "chairperson": [{"id": "P488", "label": "chairperson", "description": "chairperson of an organization, committee, or board"}],
    "chairman": [{"id": "P488", "label": "chairperson", "description": "chairperson of an organization, committee, or board"}],
    "director": [{"id": "P1037", "label": "director/manager", "description": "person who manages or directs an organization"}],
    "number of employees": [{"id": "P1128", "label": "number of employees", "description": "number of employees of an organization"}],
    "purpose": [{"id": "P1249", "label": "time period", "description": "time or period of relevance of an item"}],
    "motto": [{"id": "P1546", "label": "motto", "description": "motto of a country, organization, or group"}],
    "motto text": [{"id": "P1546", "label": "motto", "description": "motto of a country, organization, or group"}],
    "slogan": [{"id": "P1546", "label": "motto", "description": "motto of a country, organization, or group"}],
    "diplomatic relation": [{"id": "P530", "label": "diplomatic relation", "description": "diplomatic relations between two countries"}],
    "embassy": [{"id": "P530", "label": "diplomatic relation", "description": "diplomatic relations between two countries"}],
    "ambassador": [{"id": "P530", "label": "diplomatic relation", "description": "diplomatic relations between two countries"}],
    "treaty": [{"id": "P569", "label": "treaty", "description": "significant treaty or agreement"}],
    "member of": [{"id": "P463", "label": "member of", "description": "organization of which the subject is a member"}],
    "member": [{"id": "P463", "label": "member of", "description": "organization of which the subject is a member"}],
    "parent organization": [{"id": "P749", "label": "parent organization", "description": "parent organization of an organization, opposite of child organization"}],
    "follows": [{"id": "P155", "label": "follows", "description": "immediately prior item in a series"}],
    "followed by": [{"id": "P156", "label": "followed by", "description": "immediately following item in a series"}],
    "replaced by": [{"id": "P1366", "label": "replaced by", "description": "person, office, or organization that replaces the subject"}],
    "replaces": [{"id": "P1365", "label": "replaces", "description": "person, office, or organization replaced by the subject"}],
    "operating income": [{"id": "P3362", "label": "operating income", "description": "operating income of an organization"}],
    "total assets": [{"id": "P2137", "label": "total assets", "description": "total assets of an organization"}],
    "profession": [{"id": "P106", "label": "profession", "description": "occupation of a person"}],
    "academic degree": [{"id": "P512", "label": "academic degree", "description": "academic degree held by a person"}],
    "employer": [{"id": "P108", "label": "employer", "description": "person or organization for which the subject works or worked"}],
    "educated at": [{"id": "P69", "label": "educated at", "description": "educational institution attended by the subject"}],
    "head of government": [{"id": "P6", "label": "head of government", "description": "head of the executive power of a country, e.g. prime minister"}],
    "position held": [{"id": "P39", "label": "position held", "description": "position held by a person in an organization"}],
    "owned by": [{"id": "P127", "label": "owned by", "description": "owner of the subject"}],
    "part of the series": [{"id": "P179", "label": "part of the series", "description": "series which the subject is part of"}],
    "legislative body": [{"id": "P194", "label": "legislative body", "description": "legislative body of a country, state, or other territorial entity"}],
    "religion": [{"id": "P140", "label": "religion or worldview", "description": "religion of a person, organization, or religious building"}],
    "architect": [{"id": "P84", "label": "architect", "description": "architect of a building or other structure"}],
}


def get_common_properties() -> dict[str, list[dict[str, str]]]:
    """Return the pre-seeded common properties dict.

    These entries serve as a base cache so common lookups never hit the
    Wikidata API.
    """
    return dict(COMMON_PROPERTIES)

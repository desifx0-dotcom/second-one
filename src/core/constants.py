"""
Application-wide constants with 150+ language support for global SaaS platform
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List

# ========== FILE PATHS ==========
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / 'data'
UPLOADS_DIR = DATA_DIR / 'uploads'
TEMP_DIR = DATA_DIR / 'temp'
PROCESSING_DIR = DATA_DIR / 'processing'
OUTPUTS_DIR = DATA_DIR / 'outputs'
LOGS_DIR = DATA_DIR / 'logs'

# ========== COMPREHENSIVE LANGUAGE SUPPORT (150+ Languages) ==========
# Based on ISO 639-1/639-2 codes with native names and RTL/LTR support
SUPPORTED_LANGUAGES: Dict[str, Dict[str, Any]] = {
    # ========== MAJOR LANGUAGES (ISO 639-1) ==========
    'af': {'name': 'Afrikaans', 'native': 'Afrikaans', 'direction': 'ltr', 'family': 'germanic'},
    'sq': {'name': 'Albanian', 'native': 'Shqip', 'direction': 'ltr', 'family': 'albanian'},
    'am': {'name': 'Amharic', 'native': 'አማርኛ', 'direction': 'ltr', 'family': 'afro-asiatic'},
    'ar': {'name': 'Arabic', 'native': 'العربية', 'direction': 'rtl', 'family': 'afro-asiatic'},
    'hy': {'name': 'Armenian', 'native': 'Հայերեն', 'direction': 'ltr', 'family': 'armenian'},
    'az': {'name': 'Azerbaijani', 'native': 'Azərbaycanca', 'direction': 'ltr', 'family': 'turkic'},
    'eu': {'name': 'Basque', 'native': 'Euskara', 'direction': 'ltr', 'family': 'basque'},
    'be': {'name': 'Belarusian', 'native': 'Беларуская', 'direction': 'ltr', 'family': 'slavic'},
    'bn': {'name': 'Bengali', 'native': 'বাংলা', 'direction': 'ltr', 'family': 'indo-aryan'},
    'bs': {'name': 'Bosnian', 'native': 'Bosanski', 'direction': 'ltr', 'family': 'slavic'},
    'bg': {'name': 'Bulgarian', 'native': 'Български', 'direction': 'ltr', 'family': 'slavic'},
    'ca': {'name': 'Catalan', 'native': 'Català', 'direction': 'ltr', 'family': 'romance'},
    'ceb': {'name': 'Cebuano', 'native': 'Cebuano', 'direction': 'ltr', 'family': 'austronesian'},
    'zh-CN': {'name': 'Chinese (Simplified)', 'native': '简体中文', 'direction': 'ltr', 'family': 'sino-tibetan'},
    'zh-TW': {'name': 'Chinese (Traditional)', 'native': '繁體中文', 'direction': 'ltr', 'family': 'sino-tibetan'},
    'co': {'name': 'Corsican', 'native': 'Corsu', 'direction': 'ltr', 'family': 'romance'},
    'hr': {'name': 'Croatian', 'native': 'Hrvatski', 'direction': 'ltr', 'family': 'slavic'},
    'cs': {'name': 'Czech', 'native': 'Čeština', 'direction': 'ltr', 'family': 'slavic'},
    'da': {'name': 'Danish', 'native': 'Dansk', 'direction': 'ltr', 'family': 'germanic'},
    'nl': {'name': 'Dutch', 'native': 'Nederlands', 'direction': 'ltr', 'family': 'germanic'},
    'en': {'name': 'English', 'native': 'English', 'direction': 'ltr', 'family': 'germanic'},
    'eo': {'name': 'Esperanto', 'native': 'Esperanto', 'direction': 'ltr', 'family': 'constructed'},
    'et': {'name': 'Estonian', 'native': 'Eesti', 'direction': 'ltr', 'family': 'finnic'},
    'fi': {'name': 'Finnish', 'native': 'Suomi', 'direction': 'ltr', 'family': 'finnic'},
    'fr': {'name': 'French', 'native': 'Français', 'direction': 'ltr', 'family': 'romance'},
    'fy': {'name': 'Frisian', 'native': 'Frysk', 'direction': 'ltr', 'family': 'germanic'},
    'gl': {'name': 'Galician', 'native': 'Galego', 'direction': 'ltr', 'family': 'romance'},
    'ka': {'name': 'Georgian', 'native': 'ქართული', 'direction': 'ltr', 'family': 'kartvelian'},
    'de': {'name': 'German', 'native': 'Deutsch', 'direction': 'ltr', 'family': 'germanic'},
    'el': {'name': 'Greek', 'native': 'Ελληνικά', 'direction': 'ltr', 'family': 'hellenic'},
    'gu': {'name': 'Gujarati', 'native': 'ગુજરાતી', 'direction': 'ltr', 'family': 'indo-aryan'},
    'ht': {'name': 'Haitian Creole', 'native': 'Kreyòl Ayisyen', 'direction': 'ltr', 'family': 'creole'},
    'ha': {'name': 'Hausa', 'native': 'Hausa', 'direction': 'ltr', 'family': 'afro-asiatic'},
    'haw': {'name': 'Hawaiian', 'native': 'ʻŌlelo Hawaiʻi', 'direction': 'ltr', 'family': 'austronesian'},
    'he': {'name': 'Hebrew', 'native': 'עברית', 'direction': 'rtl', 'family': 'afro-asiatic'},
    'hi': {'name': 'Hindi', 'native': 'हिन्दी', 'direction': 'ltr', 'family': 'indo-aryan'},
    'hmn': {'name': 'Hmong', 'native': 'Hmoob', 'direction': 'ltr', 'family': 'hmong-mien'},
    'hu': {'name': 'Hungarian', 'native': 'Magyar', 'direction': 'ltr', 'family': 'uralic'},
    'is': {'name': 'Icelandic', 'native': 'Íslenska', 'direction': 'ltr', 'family': 'germanic'},
    'ig': {'name': 'Igbo', 'native': 'Igbo', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'id': {'name': 'Indonesian', 'native': 'Bahasa Indonesia', 'direction': 'ltr', 'family': 'austronesian'},
    'ga': {'name': 'Irish', 'native': 'Gaeilge', 'direction': 'ltr', 'family': 'celtic'},
    'it': {'name': 'Italian', 'native': 'Italiano', 'direction': 'ltr', 'family': 'romance'},
    'ja': {'name': 'Japanese', 'native': '日本語', 'direction': 'ltr', 'family': 'japonic'},
    'jv': {'name': 'Javanese', 'native': 'Basa Jawa', 'direction': 'ltr', 'family': 'austronesian'},
    'kn': {'name': 'Kannada', 'native': 'ಕನ್ನಡ', 'direction': 'ltr', 'family': 'dravidian'},
    'kk': {'name': 'Kazakh', 'native': 'Қазақ тілі', 'direction': 'ltr', 'family': 'turkic'},
    'km': {'name': 'Khmer', 'native': 'ភាសាខ្មែរ', 'direction': 'ltr', 'family': 'austroasiatic'},
    'rw': {'name': 'Kinyarwanda', 'native': 'Kinyarwanda', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'ko': {'name': 'Korean', 'native': '한국어', 'direction': 'ltr', 'family': 'koreanic'},
    'ku': {'name': 'Kurdish', 'native': 'Kurdî', 'direction': 'rtl', 'family': 'iranian'},
    'ky': {'name': 'Kyrgyz', 'native': 'Кыргызча', 'direction': 'ltr', 'family': 'turkic'},
    'lo': {'name': 'Lao', 'native': 'ລາວ', 'direction': 'ltr', 'family': 'kra-dai'},
    'lv': {'name': 'Latvian', 'native': 'Latviešu', 'direction': 'ltr', 'family': 'baltic'},
    'lt': {'name': 'Lithuanian', 'native': 'Lietuvių', 'direction': 'ltr', 'family': 'baltic'},
    'lb': {'name': 'Luxembourgish', 'native': 'Lëtzebuergesch', 'direction': 'ltr', 'family': 'germanic'},
    'mk': {'name': 'Macedonian', 'native': 'Македонски', 'direction': 'ltr', 'family': 'slavic'},
    'mg': {'name': 'Malagasy', 'native': 'Malagasy', 'direction': 'ltr', 'family': 'austronesian'},
    'ms': {'name': 'Malay', 'native': 'Bahasa Melayu', 'direction': 'ltr', 'family': 'austronesian'},
    'ml': {'name': 'Malayalam', 'native': 'മലയാളം', 'direction': 'ltr', 'family': 'dravidian'},
    'mt': {'name': 'Maltese', 'native': 'Malti', 'direction': 'ltr', 'family': 'afro-asiatic'},
    'mi': {'name': 'Maori', 'native': 'Māori', 'direction': 'ltr', 'family': 'austronesian'},
    'mr': {'name': 'Marathi', 'native': 'मराठी', 'direction': 'ltr', 'family': 'indo-aryan'},
    'mn': {'name': 'Mongolian', 'native': 'Монгол', 'direction': 'ltr', 'family': 'mongolic'},
    'my': {'name': 'Myanmar (Burmese)', 'native': 'မြန်မာစာ', 'direction': 'ltr', 'family': 'sino-tibetan'},
    'ne': {'name': 'Nepali', 'native': 'नेपाली', 'direction': 'ltr', 'family': 'indo-aryan'},
    'no': {'name': 'Norwegian', 'native': 'Norsk', 'direction': 'ltr', 'family': 'germanic'},
    'ny': {'name': 'Nyanja (Chichewa)', 'native': 'Chicheŵa', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'or': {'name': 'Odia (Oriya)', 'native': 'ଓଡ଼ିଆ', 'direction': 'ltr', 'family': 'indo-aryan'},
    'ps': {'name': 'Pashto', 'native': 'پښتو', 'direction': 'rtl', 'family': 'iranian'},
    'fa': {'name': 'Persian', 'native': 'فارسی', 'direction': 'rtl', 'family': 'iranian'},
    'pl': {'name': 'Polish', 'native': 'Polski', 'direction': 'ltr', 'family': 'slavic'},
    'pt': {'name': 'Portuguese', 'native': 'Português', 'direction': 'ltr', 'family': 'romance'},
    'pa': {'name': 'Punjabi', 'native': 'ਪੰਜਾਬੀ', 'direction': 'ltr', 'family': 'indo-aryan'},
    'ro': {'name': 'Romanian', 'native': 'Română', 'direction': 'ltr', 'family': 'romance'},
    'ru': {'name': 'Russian', 'native': 'Русский', 'direction': 'ltr', 'family': 'slavic'},
    'sm': {'name': 'Samoan', 'native': 'Gagana Samoa', 'direction': 'ltr', 'family': 'austronesian'},
    'gd': {'name': 'Scots Gaelic', 'native': 'Gàidhlig', 'direction': 'ltr', 'family': 'celtic'},
    'sr': {'name': 'Serbian', 'native': 'Српски', 'direction': 'ltr', 'family': 'slavic'},
    'st': {'name': 'Sesotho', 'native': 'Sesotho', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'sn': {'name': 'Shona', 'native': 'Shona', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'sd': {'name': 'Sindhi', 'native': 'سنڌي', 'direction': 'rtl', 'family': 'indo-aryan'},
    'si': {'name': 'Sinhala', 'native': 'සිංහල', 'direction': 'ltr', 'family': 'indo-aryan'},
    'sk': {'name': 'Slovak', 'native': 'Slovenčina', 'direction': 'ltr', 'family': 'slavic'},
    'sl': {'name': 'Slovenian', 'native': 'Slovenščina', 'direction': 'ltr', 'family': 'slavic'},
    'so': {'name': 'Somali', 'native': 'Soomaali', 'direction': 'ltr', 'family': 'afro-asiatic'},
    'es': {'name': 'Spanish', 'native': 'Español', 'direction': 'ltr', 'family': 'romance'},
    'su': {'name': 'Sundanese', 'native': 'Basa Sunda', 'direction': 'ltr', 'family': 'austronesian'},
    'sw': {'name': 'Swahili', 'native': 'Kiswahili', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'sv': {'name': 'Swedish', 'native': 'Svenska', 'direction': 'ltr', 'family': 'germanic'},
    'tl': {'name': 'Tagalog', 'native': 'Tagalog', 'direction': 'ltr', 'family': 'austronesian'},
    'tg': {'name': 'Tajik', 'native': 'Тоҷикӣ', 'direction': 'ltr', 'family': 'iranian'},
    'ta': {'name': 'Tamil', 'native': 'தமிழ்', 'direction': 'ltr', 'family': 'dravidian'},
    'tt': {'name': 'Tatar', 'native': 'Татарча', 'direction': 'ltr', 'family': 'turkic'},
    'te': {'name': 'Telugu', 'native': 'తెలుగు', 'direction': 'ltr', 'family': 'dravidian'},
    'th': {'name': 'Thai', 'native': 'ไทย', 'direction': 'ltr', 'family': 'kra-dai'},
    'tr': {'name': 'Turkish', 'native': 'Türkçe', 'direction': 'ltr', 'family': 'turkic'},
    'tk': {'name': 'Turkmen', 'native': 'Türkmençe', 'direction': 'ltr', 'family': 'turkic'},
    'uk': {'name': 'Ukrainian', 'native': 'Українська', 'direction': 'ltr', 'family': 'slavic'},
    'ur': {'name': 'Urdu', 'native': 'اردو', 'direction': 'rtl', 'family': 'indo-aryan'},
    'ug': {'name': 'Uyghur', 'native': 'ئۇيغۇرچە', 'direction': 'rtl', 'family': 'turkic'},
    'uz': {'name': 'Uzbek', 'native': 'Oʻzbekcha', 'direction': 'ltr', 'family': 'turkic'},
    'vi': {'name': 'Vietnamese', 'native': 'Tiếng Việt', 'direction': 'ltr', 'family': 'austroasiatic'},
    'cy': {'name': 'Welsh', 'native': 'Cymraeg', 'direction': 'ltr', 'family': 'celtic'},
    'xh': {'name': 'Xhosa', 'native': 'isiXhosa', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'yi': {'name': 'Yiddish', 'native': 'ייִדיש', 'direction': 'rtl', 'family': 'germanic'},
    'yo': {'name': 'Yoruba', 'native': 'Yorùbá', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'zu': {'name': 'Zulu', 'native': 'isiZulu', 'direction': 'ltr', 'family': 'atlantic-congo'},
    
    # ========== REGIONAL & LESSER-KNOWN LANGUAGES ==========
    'ab': {'name': 'Abkhazian', 'native': 'Аҧсуа', 'direction': 'ltr', 'family': 'northwest-caucasian'},
    'aa': {'name': 'Afar', 'native': 'Afaraf', 'direction': 'ltr', 'family': 'afro-asiatic'},
    'ak': {'name': 'Akan', 'native': 'Akan', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'an': {'name': 'Aragonese', 'native': 'Aragonés', 'direction': 'ltr', 'family': 'romance'},
    'as': {'name': 'Assamese', 'native': 'অসমীয়া', 'direction': 'ltr', 'family': 'indo-aryan'},
    'av': {'name': 'Avaric', 'native': 'Авар мацӀ', 'direction': 'ltr', 'family': 'northeast-caucasian'},
    'ae': {'name': 'Avestan', 'native': 'Avesta', 'direction': 'rtl', 'family': 'iranian'},
    'ay': {'name': 'Aymara', 'native': 'Aymar aru', 'direction': 'ltr', 'family': 'aymara'},
    'ba': {'name': 'Bashkir', 'native': 'Башҡорт теле', 'direction': 'ltr', 'family': 'turkic'},
    'bi': {'name': 'Bislama', 'native': 'Bislama', 'direction': 'ltr', 'family': 'creole'},
    'br': {'name': 'Breton', 'native': 'Brezhoneg', 'direction': 'ltr', 'family': 'celtic'},
    'ch': {'name': 'Chamorro', 'native': 'Chamoru', 'direction': 'ltr', 'family': 'austronesian'},
    'cu': {'name': 'Church Slavic', 'native': 'Ѩзыкъ словѣньскъ', 'direction': 'ltr', 'family': 'slavic'},
    'cv': {'name': 'Chuvash', 'native': 'Чӑваш чӗлхи', 'direction': 'ltr', 'family': 'turkic'},
    'kw': {'name': 'Cornish', 'native': 'Kernewek', 'direction': 'ltr', 'family': 'celtic'},
    'cr': {'name': 'Cree', 'native': 'ᓀᐦᐃᔭᐍᐏᐣ', 'direction': 'ltr', 'family': 'algonquian'},
    'dv': {'name': 'Divehi', 'native': 'ދިވެހި', 'direction': 'rtl', 'family': 'indo-aryan'},
    'dz': {'name': 'Dzongkha', 'native': 'རྫོང་ཁ', 'direction': 'ltr', 'family': 'sino-tibetan'},
    'ee': {'name': 'Ewe', 'native': 'Eʋegbe', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'fo': {'name': 'Faroese', 'native': 'Føroyskt', 'direction': 'ltr', 'family': 'germanic'},
    'fj': {'name': 'Fijian', 'native': 'Vosa Vakaviti', 'direction': 'ltr', 'family': 'austronesian'},
    'ff': {'name': 'Fulah', 'native': 'Fulfulde', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'gn': {'name': 'Guarani', 'native': 'Avañe\'ẽ', 'direction': 'ltr', 'family': 'tupi-guarani'},
    'gv': {'name': 'Manx', 'native': 'Gaelg', 'direction': 'ltr', 'family': 'celtic'},
    'hz': {'name': 'Herero', 'native': 'Otjiherero', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'ho': {'name': 'Hiri Motu', 'native': 'Hiri Motu', 'direction': 'ltr', 'family': 'austronesian'},
    'ia': {'name': 'Interlingua', 'native': 'Interlingua', 'direction': 'ltr', 'family': 'constructed'},
    'ie': {'name': 'Interlingue', 'native': 'Interlingue', 'direction': 'ltr', 'family': 'constructed'},
    'iu': {'name': 'Inuktitut', 'native': 'ᐃᓄᒃᑎᑐᑦ', 'direction': 'ltr', 'family': 'eskimo-aleut'},
    'ik': {'name': 'Inupiaq', 'native': 'Iñupiaq', 'direction': 'ltr', 'family': 'eskimo-aleut'},
    'kl': {'name': 'Kalaallisut', 'native': 'Kalaallisut', 'direction': 'ltr', 'family': 'eskimo-aleut'},
    'ks': {'name': 'Kashmiri', 'native': 'कॉशुर', 'direction': 'rtl', 'family': 'indo-aryan'},
    'ki': {'name': 'Kikuyu', 'native': 'Gĩkũyũ', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'kj': {'name': 'Kuanyama', 'native': 'Kwanyama', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'la': {'name': 'Latin', 'native': 'Latina', 'direction': 'ltr', 'family': 'italic'},
    'lg': {'name': 'Ganda', 'native': 'Luganda', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'li': {'name': 'Limburgish', 'native': 'Limburgs', 'direction': 'ltr', 'family': 'germanic'},
    'ln': {'name': 'Lingala', 'native': 'Lingála', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'lu': {'name': 'Luba-Katanga', 'native': 'Kiluba', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'mh': {'name': 'Marshallese', 'native': 'Kajin M̧ajeļ', 'direction': 'ltr', 'family': 'austronesian'},
    'na': {'name': 'Nauru', 'native': 'Dorerin Naoero', 'direction': 'ltr', 'family': 'austronesian'},
    'nv': {'name': 'Navajo', 'native': 'Diné bizaad', 'direction': 'ltr', 'family': 'na-dene'},
    'ng': {'name': 'Ndonga', 'native': 'Owambo', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'nd': {'name': 'North Ndebele', 'native': 'isiNdebele', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'nr': {'name': 'South Ndebele', 'native': 'isiNdebele', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'oc': {'name': 'Occitan', 'native': 'Occitan', 'direction': 'ltr', 'family': 'romance'},
    'oj': {'name': 'Ojibwa', 'native': 'ᐊᓂᔑᓈᐯᒧᐎᓐ', 'direction': 'ltr', 'family': 'algonquian'},
    'om': {'name': 'Oromo', 'native': 'Afaan Oromoo', 'direction': 'ltr', 'family': 'afro-asiatic'},
    'os': {'name': 'Ossetian', 'native': 'Ирон æвзаг', 'direction': 'ltr', 'family': 'iranian'},
    'pi': {'name': 'Pali', 'native': 'पालि', 'direction': 'ltr', 'family': 'indo-aryan'},
    'qu': {'name': 'Quechua', 'native': 'Runa Simi', 'direction': 'ltr', 'family': 'quechuan'},
    'rm': {'name': 'Romansh', 'native': 'Rumantsch', 'direction': 'ltr', 'family': 'romance'},
    'rn': {'name': 'Rundi', 'native': 'Ikirundi', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'sc': {'name': 'Sardinian', 'native': 'Sardu', 'direction': 'ltr', 'family': 'romance'},
    'sg': {'name': 'Sango', 'native': 'Sängö', 'direction': 'ltr', 'family': 'creole'},
    'sa': {'name': 'Sanskrit', 'native': 'संस्कृतम्', 'direction': 'ltr', 'family': 'indo-aryan'},
    'ss': {'name': 'Swati', 'native': 'SiSwati', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'ti': {'name': 'Tigrinya', 'native': 'ትግርኛ', 'direction': 'ltr', 'family': 'afro-asiatic'},
    'bo': {'name': 'Tibetan', 'native': 'བོད་སྐད་', 'direction': 'ltr', 'family': 'sino-tibetan'},
    'ts': {'name': 'Tsonga', 'native': 'Xitsonga', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'tn': {'name': 'Tswana', 'native': 'Setswana', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'to': {'name': 'Tonga', 'native': 'Lea faka-Tonga', 'direction': 'ltr', 'family': 'austronesian'},
    'ty': {'name': 'Tahitian', 'native': 'Reo Tahiti', 'direction': 'ltr', 'family': 'austronesian'},
    've': {'name': 'Venda', 'native': 'Tshivenḓa', 'direction': 'ltr', 'family': 'atlantic-congo'},
    'vo': {'name': 'Volapük', 'native': 'Volapük', 'direction': 'ltr', 'family': 'constructed'},
    'wa': {'name': 'Walloon', 'native': 'Walon', 'direction': 'ltr', 'family': 'romance'},
    'wo': {'name': 'Wolof', 'native': 'Wolof', 'direction': 'ltr', 'family': 'atlantic-congo'},
}

# ========== LANGUAGE UTILITY FUNCTIONS ==========
def get_language_name(code: str) -> str:
    """Get language name from code"""
    return SUPPORTED_LANGUAGES.get(code, {}).get('name', 'Unknown')

def get_native_name(code: str) -> str:
    """Get native language name from code"""
    return SUPPORTED_LANGUAGES.get(code, {}).get('native', code)

def get_language_direction(code: str) -> str:
    """Get text direction (ltr/rtl) for language"""
    return SUPPORTED_LANGUAGES.get(code, {}).get('direction', 'ltr')

def get_language_family(code: str) -> str:
    """Get language family"""
    return SUPPORTED_LANGUAGES.get(code, {}).get('family', 'unknown')

def get_popular_languages() -> List[Dict[str, Any]]:
    """Get list of most popular languages for UI dropdowns"""
    popular_codes = ['en', 'es', 'fr', 'de', 'zh-CN', 'zh-TW', 'hi', 'ar', 'ru', 'pt', 'ja', 'ko', 'it']
    return [
        {'code': code, **SUPPORTED_LANGUAGES[code]}
        for code in popular_codes if code in SUPPORTED_LANGUAGES
    ]

def get_all_languages_sorted() -> List[Dict[str, Any]]:
    """Get all languages sorted by name"""
    sorted_items = sorted(
        [(code, data) for code, data in SUPPORTED_LANGUAGES.items()],
        key=lambda x: x[1]['name']
    )
    return [{'code': code, **data} for code, data in sorted_items]

# ========== FILE FORMATS ==========
class VideoFormat(Enum):
    MP4 = 'mp4'
    MOV = 'mov'
    AVI = 'avi'
    MKV = 'mkv'
    WEBM = 'webm'
    FLV = 'flv'
    WMV = 'wmv'
    MPEG = 'mpeg'
    MPG = 'mpg'
    M4V = 'm4v'
    _3GP = '3gp'
    _3G2 = '3g2'

class AudioFormat(Enum):
    MP3 = 'mp3'
    WAV = 'wav'
    M4A = 'm4a'
    FLAC = 'flac'
    AAC = 'aac'
    OGG = 'ogg'
    WMA = 'wma'
    AIFF = 'aiff'
    AU = 'au'
    RA = 'ra'
    RM = 'rm'
    VOC = 'voc'

VIDEO_FORMATS = {fmt.value for fmt in VideoFormat}
AUDIO_FORMATS = {fmt.value for fmt in AudioFormat}
ALLOWED_FORMATS = VIDEO_FORMATS.union(AUDIO_FORMATS)

# ========== SUBSCRIPTION TIERS ==========
class SubscriptionTier(Enum):
    FREE = 'free'
    PLUS = 'plus'
    PRO = 'pro'
    ENTERPRISE = 'enterprise'

SUBSCRIPTION_TIERS = {
    'free': {
        'name': 'Free',
        'videos_per_month': 3,
        'max_file_size_mb': 100,
        'max_duration_minutes': 10,
        'features': ['Basic Transcription', 'Manual Titles', 'Standard Thumbnails'],
        'price_monthly': 0.00,
        'price_yearly': 0.00,
    },
    'plus': {
        'name': 'Plus',
        'videos_per_month': 50,
        'max_file_size_mb': 500,
        'max_duration_minutes': 30,
        'features': ['AI Titles', 'Auto Thumbnails', 'Multi-Language Support', 'Priority Processing'],
        'price_monthly': 19.99,
        'price_yearly': 199.99,  # ~2 months free
    },
    'pro': {
        'name': 'Pro',
        'videos_per_month': 500,
        'max_file_size_gb': 2,
        'max_duration_minutes': 120,
        'features': ['AI Summaries', 'Chapter Generation', 'API Access', 'Custom Branding', 'Bulk Processing'],
        'price_monthly': 49.99,
        'price_yearly': 499.99,  # ~2 months free
    },
    'enterprise': {
        'name': 'Enterprise',
        'videos_per_month': 'Unlimited',
        'max_file_size_gb': 10,
        'max_duration_minutes': 240,
        'features': ['Custom AI Models', 'Dedicated Support', 'SLA Guarantee', 'On-premise Deployment', 'Custom Workflows'],
        'price_monthly': 199.99,
        'price_yearly': 1999.99,  # ~2 months free
    }
}

# ========== PROCESSING CONSTANTS ==========
class ProcessingStatus(Enum):
    PENDING = 'pending'
    UPLOADING = 'uploading'
    QUEUED = 'queued'
    PROCESSING = 'processing'
    TRANSCRIBING = 'transcribing'
    GENERATING_TITLES = 'generating_titles'
    GENERATING_THUMBNAILS = 'generating_thumbnails'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

PROCESSING_STATUSES = [status.value for status in ProcessingStatus]

# ========== API CONSTANTS ==========
API_RATE_LIMITS = {
    'free': {'per_day': 100, 'per_hour': 10, 'per_minute': 2},
    'plus': {'per_day': 1000, 'per_hour': 100, 'per_minute': 10},
    'pro': {'per_day': 10000, 'per_hour': 1000, 'per_minute': 100},
    'enterprise': {'per_day': 100000, 'per_hour': 10000, 'per_minute': 1000},
}

# ========== AI MODEL CONSTANTS ==========
AI_MODELS = {
    'transcription': {
        'whisper': {'name': 'OpenAI Whisper', 'languages': list(SUPPORTED_LANGUAGES.keys()), 'accuracy': 'high'},
        'google': {'name': 'Google Speech-to-Text', 'languages': ['en', 'es', 'fr', 'de', 'zh', 'ja', 'ko'], 'accuracy': 'high'},
        'assemblyai': {'name': 'AssemblyAI', 'languages': ['en'], 'accuracy': 'very-high'},
    },
    'translation': {
        'google': {'name': 'Google Translate', 'languages': list(SUPPORTED_LANGUAGES.keys()), 'accuracy': 'high'},
        'deepl': {'name': 'DeepL', 'languages': ['en', 'de', 'fr', 'es', 'pt', 'it', 'nl', 'pl', 'ru', 'ja', 'zh'], 'accuracy': 'very-high'},
        'openai': {'name': 'OpenAI GPT', 'languages': list(SUPPORTED_LANGUAGES.keys()), 'accuracy': 'very-high'},
    },
    'title_generation': {
        'gpt4': {'name': 'GPT-4', 'max_tokens': 100, 'temperature': 0.7},
        'claude': {'name': 'Claude', 'max_tokens': 150, 'temperature': 0.6},
        'gemini': {'name': 'Google Gemini', 'max_tokens': 120, 'temperature': 0.5},
    },
    'thumbnail_generation': {
        'stability': {'name': 'Stability AI', 'style': 'realistic', 'resolution': '1024x1024'},
        'dalle': {'name': 'DALL-E', 'style': 'artistic', 'resolution': '1024x1024'},
        'midjourney': {'name': 'Midjourney', 'style': 'creative', 'resolution': '1024x1024'},
    }
}

# ========== VIDEO QUALITY CONSTANTS ==========
class VideoQuality(Enum):
    LOW = {'name': 'Low', 'resolution': '480p', 'bitrate': '1000k'}
    MEDIUM = {'name': 'Medium', 'resolution': '720p', 'bitrate': '2500k'}
    HIGH = {'name': 'High', 'resolution': '1080p', 'bitrate': '5000k'}
    UHD = {'name': 'Ultra HD', 'resolution': '4K', 'bitrate': '15000k'}

# ========== THUMBNAIL STYLES ==========
THUMBNAIL_STYLES = {
    'cinematic': {'name': 'Cinematic', 'brightness': 0.9, 'contrast': 1.2, 'saturation': 1.1},
    'minimal': {'name': 'Minimal', 'brightness': 1.0, 'contrast': 1.0, 'saturation': 0.8},
    'vibrant': {'name': 'Vibrant', 'brightness': 1.1, 'contrast': 1.3, 'saturation': 1.4},
    'dark': {'name': 'Dark Mode', 'brightness': 0.7, 'contrast': 1.1, 'saturation': 0.9},
    'bright': {'name': 'Bright', 'brightness': 1.2, 'contrast': 1.0, 'saturation': 1.0},
    'retro': {'name': 'Retro', 'brightness': 0.8, 'contrast': 1.4, 'saturation': 0.7},
}

# ========== TIME CONSTANTS ==========
class TimeConstants:
    SECOND = 1
    MINUTE = 60
    HOUR = 3600
    DAY = 86400
    WEEK = 604800
    MONTH_30_DAYS = 2592000
    YEAR_365_DAYS = 31536000

# ========== STORAGE CONSTANTS ==========
class StorageConstants:
    BYTE = 1
    KILOBYTE = 1024
    MEGABYTE = 1048576
    GIGABYTE = 1073741824
    TERABYTE = 1099511627776

# ========== SECURITY CONSTANTS ==========
class SecurityConstants:
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 128
    TOKEN_EXPIRY_HOURS = 24
    API_KEY_EXPIRY_DAYS = 365
    SESSION_TIMEOUT_MINUTES = 30
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

# ========== ERROR CODES ==========
class ErrorCodes:
    # Authentication errors (1000-1099)
    AUTH_INVALID_CREDENTIALS = 1001
    AUTH_TOKEN_EXPIRED = 1002
    AUTH_TOKEN_INVALID = 1003
    AUTH_INSUFFICIENT_PERMISSIONS = 1004
    AUTH_RATE_LIMITED = 1005
    
    # Validation errors (1100-1199)
    VALIDATION_INVALID_INPUT = 1101
    VALIDATION_FILE_TOO_LARGE = 1102
    VALIDATION_UNSUPPORTED_FORMAT = 1103
    VALIDATION_INVALID_EMAIL = 1104
    VALIDATION_WEAK_PASSWORD = 1105
    
    # Processing errors (1200-1299)
    PROCESSING_FAILED = 1201
    PROCESSING_TIMEOUT = 1202
    PROCESSING_QUOTA_EXCEEDED = 1203
    PROCESSING_FILE_CORRUPT = 1204
    PROCESSING_UNSUPPORTED_LANGUAGE = 1205
    
    # Payment errors (1300-1399)
    PAYMENT_FAILED = 1301
    PAYMENT_CARD_DECLINED = 1302
    PAYMENT_INSUFFICIENT_FUNDS = 1303
    PAYMENT_SUBSCRIPTION_EXPIRED = 1304
    
    # System errors (1400-1499)
    SYSTEM_DATABASE_ERROR = 1401
    SYSTEM_EXTERNAL_API_ERROR = 1402
    SYSTEM_STORAGE_ERROR = 1403
    SYSTEM_MAINTENANCE = 1404
    SYSTEM_OVERLOADED = 1405

# ========== ENVIRONMENT CONSTANTS ==========
class Environment(Enum):
    DEVELOPMENT = 'development'
    STAGING = 'staging'
    PRODUCTION = 'production'
    TESTING = 'testing'

# ========== EXPORT CONSTANTS ==========
EXPORT_FORMATS = {
    'srt': {'name': 'SubRip (.srt)', 'mime': 'text/plain'},
    'vtt': {'name': 'WebVTT (.vtt)', 'mime': 'text/vtt'},
    'txt': {'name': 'Plain Text (.txt)', 'mime': 'text/plain'},
    'json': {'name': 'JSON (.json)', 'mime': 'application/json'},
    'csv': {'name': 'CSV (.csv)', 'mime': 'text/csv'},
    'pdf': {'name': 'PDF (.pdf)', 'mime': 'application/pdf'},
}

# ========== MIME TYPE MAPPINGS ==========
MIME_TYPES = {
    # Video
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
    'avi': 'video/x-msvideo',
    'mkv': 'video/x-matroska',
    'webm': 'video/webm',
    'flv': 'video/x-flv',
    'wmv': 'video/x-ms-wmv',
    'mpeg': 'video/mpeg',
    'mpg': 'video/mpeg',
    'm4v': 'video/x-m4v',
    '3gp': 'video/3gpp',
    '3g2': 'video/3gpp2',
    
    # Audio
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav',
    'm4a': 'audio/mp4',
    'flac': 'audio/flac',
    'aac': 'audio/aac',
    'ogg': 'audio/ogg',
    'wma': 'audio/x-ms-wma',
    'aiff': 'audio/x-aiff',
    'au': 'audio/basic',
    
    # Images
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'bmp': 'image/bmp',
    'svg': 'image/svg+xml',
    
    # Documents
    'pdf': 'application/pdf',
    'txt': 'text/plain',
    'json': 'application/json',
    'csv': 'text/csv',
    'srt': 'text/plain',
    'vtt': 'text/vtt',
}

# ========== COUNTRY CODES (For regional pricing) ==========
# ISO 3166-1 alpha-2 country codes
SUPPORTED_COUNTRIES = {
    'US': {'name': 'United States', 'currency': 'USD', 'vat_rate': 0.0},
    'GB': {'name': 'United Kingdom', 'currency': 'GBP', 'vat_rate': 0.2},
    'DE': {'name': 'Germany', 'currency': 'EUR', 'vat_rate': 0.19},
    'FR': {'name': 'France', 'currency': 'EUR', 'vat_rate': 0.2},
    'ES': {'name': 'Spain', 'currency': 'EUR', 'vat_rate': 0.21},
    'IT': {'name': 'Italy', 'currency': 'EUR', 'vat_rate': 0.22},
    'CA': {'name': 'Canada', 'currency': 'CAD', 'vat_rate': 0.05},
    'AU': {'name': 'Australia', 'currency': 'AUD', 'vat_rate': 0.1},
    'JP': {'name': 'Japan', 'currency': 'JPY', 'vat_rate': 0.1},
    'IN': {'name': 'India', 'currency': 'INR', 'vat_rate': 0.18},
    'CN': {'name': 'China', 'currency': 'CNY', 'vat_rate': 0.13},
    'BR': {'name': 'Brazil', 'currency': 'BRL', 'vat_rate': 0.17},
    'MX': {'name': 'Mexico', 'currency': 'MXN', 'vat_rate': 0.16},
    'RU': {'name': 'Russia', 'currency': 'RUB', 'vat_rate': 0.2},
    'ZA': {'name': 'South Africa', 'currency': 'ZAR', 'vat_rate': 0.15},
    'AE': {'name': 'United Arab Emirates', 'currency': 'AED', 'vat_rate': 0.05},
    'SA': {'name': 'Saudi Arabia', 'currency': 'SAR', 'vat_rate': 0.15},
    'SG': {'name': 'Singapore', 'currency': 'SGD', 'vat_rate': 0.07},
    'KR': {'name': 'South Korea', 'currency': 'KRW', 'vat_rate': 0.1},
}

# ========== TIMEZONES ==========
POPULAR_TIMEZONES = [
    'UTC',
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'Europe/London',
    'Europe/Paris',
    'Europe/Berlin',
    'Europe/Moscow',
    'Asia/Dubai',
    'Asia/Kolkata',
    'Asia/Shanghai',
    'Asia/Tokyo',
    'Australia/Sydney',
    'Pacific/Auckland',
]

# ========== MONITORING CONSTANTS ==========
class MonitoringConstants:
    METRICS_INTERVAL_SECONDS = 60
    HEALTH_CHECK_INTERVAL_SECONDS = 30
    ALERT_THRESHOLD_PROCESSING_TIME = 300  # 5 minutes
    ALERT_THRESHOLD_ERROR_RATE = 0.05  # 5%
    ALERT_THRESHOLD_QUEUE_SIZE = 100
    ALERT_THRESHOLD_MEMORY_USAGE = 0.8  # 80%
    ALERT_THRESHOLD_DISK_USAGE = 0.9  # 90%

# ========== EXPORT ALL ==========
__all__ = [
    # Core paths
    'BASE_DIR', 'DATA_DIR', 'UPLOADS_DIR', 'TEMP_DIR', 'PROCESSING_DIR', 'OUTPUTS_DIR', 'LOGS_DIR',
    
    # Languages
    'SUPPORTED_LANGUAGES',
    'get_language_name', 'get_native_name', 'get_language_direction', 'get_language_family',
    'get_popular_languages', 'get_all_languages_sorted',
    
    # File formats
    'VideoFormat', 'AudioFormat', 'VIDEO_FORMATS', 'AUDIO_FORMATS', 'ALLOWED_FORMATS',
    
    # Subscriptions
    'SubscriptionTier', 'SUBSCRIPTION_TIERS',
    
    # Processing
    'ProcessingStatus', 'PROCESSING_STATUSES', 'AI_MODELS',
    
    # API
    'API_RATE_LIMITS',
    
    # Quality & Styles
    'VideoQuality', 'THUMBNAIL_STYLES',
    
    # Time & Storage
    'TimeConstants', 'StorageConstants',
    
    # Security
    'SecurityConstants',
    
    # Errors
    'ErrorCodes',
    
    # Environment
    'Environment',
    
    # Export
    'EXPORT_FORMATS', 'MIME_TYPES',
    
    # Countries & Timezones
    'SUPPORTED_COUNTRIES', 'POPULAR_TIMEZONES',
    
    # Monitoring
    'MonitoringConstants',
]
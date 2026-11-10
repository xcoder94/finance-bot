"""Appendix A cascade keyword dictionary (translation_key -> RU+UZ terms).

UZ terms: Latin (apostrophe-normalised by the prefilter, so typographic variants also match) and common
Cyrillic-Uzbek. Matching is whole-word and case-insensitive; a message that matches two
categories falls through to the model, so a term must not be shared by unrelated categories.
"""

from __future__ import annotations

CASCADE_KEYWORDS: dict[str, list[str]] = {
    "food": [
        "еда", "ovqat", "taom", "ovqatlanish", "овқат", "таом",
    ],
    "groceries": [
        "продукты", "магазин", "супермаркет", "oziq-ovqat", "market", "do'kon", "dokon",
        "bozorlik", "bozorli", "bozor", "bozorga", "ro'zg'or", "rozgor", "magazin", "korzinka",
        "oziq ovqat", "supermarket", "produkt", "mahsulot", "non", "sut", "go'sht", "gosht",
        "meva", "sabzavot", "maqazin", "бозорлик", "бозор", "дўкон", "маркет", "озиқ-овқат",
        "озиқ овқат", "нон", "сут", "гўшт", "мева",
    ],
    "cafes_restaurants": [
        "кафе", "ресторан", "кофе", "обед", "завтрок", "ужин", "kafe", "restoran", "taomxona",
        "obet", "obed", "milliy taom", "ujn", "zavtrok", "lavash", "fasfud", "somsa", "osh",
        "tushlik", "nonushta", "kechki ovqat", "choyxona", "oshxona", "kofe", "coffee",
        "restoranga", "kafega", "чойхона", "ошхона", "тушлик", "нонушта", "ош", "сомса",
        "ресторанга", "кафега",
    ],
    "delivery": [
        "доставка", "яндекс еда", "uzum tezkor", "yetkazib berish", "dostavka", "delivery",
        "wolt", "express24", "express 24", "yandeks ovqat", "yetkazish", "етказиб бериш",
    ],
    "transport": [
        "транспорт", "автобус", "метро", "марштрутка", "дамас", "transport", "avtobus", "metro",
        "yo'l", "yol", "йўл",
    ],
    "taxi": [
        "такси", "яндекс такси", "болт", "taksi", "taxi", "taksiga", "yandex", "yandex go",
        "yandex taksi", "yandexgo", "indrive", "in drive", "bolt", "mytaxi", "my taxi",
        "taksida", "яндекс", "яндекс го", "индрайв", "таксига",
    ],
    "fuel": [
        "бензин", "заправка", "топливо", "газ (авто)", "газ метан", "метан газ", "метан",
        "газ пропан", "пропан газ", "пропан", "benzin", "yoqilg'i", "benzinga", "yoqilgi",
        "dizel", "zapravka", "zapravkaga", "ai 92", "ai-92", "ai92", "ai 95", "ai-95", "ai95",
        "солярка", "дизель", "бензинга", "ёқилғи", "заправкага",
    ],
    "public_transport": [
        "автобус", "метро", "маршрутка", "проезд", "avtobus", "metro", "avtobusga", "metroga",
        "marshrutka", "marshrutkaga", "marshrut", "yo'l kira", "yol kira", "yo'lkira",
        "yo'l haqi", "yo'l puli", "автобусга", "метрога", "йўл кира", "йул кира",
    ],
    "car_maintenance": [
        "сто", "автосервис", "шиномонтаж", "мойка", "avto servis", "moyka", "moshina arenda",
        "avtoservis", "avtomoyka", "avto moyka", "mashina yuvish", "mashina ta'miri",
        "mashina tamiri", "moshina ta'miri", "texnik xizmat", "moy almashtirish", "moy",
        "shina", "zapchast", "zapchastlar", "ehtiyot qismlar", "akkumulyator", "avtoservisga",
        "автомойка", "запчасти", "запчасть", "техник хизмат", "мой алмаштириш",
    ],
    "home": [
        "дом", "uy", "hovli", "xovli", "dacha", "дача", "дачу", "уй", "ховли", "uy-joy",
        "uy joy",
    ],
    "rent": [
        "аренда", "съём квартиры", "ijara", "kvartira arenda", "arenda", "kvartira",
        "kvartira ijara", "uy ijarasi", "ijaraga", "ijara haqi", "ijara puli", "ижара",
        "квартира", "ижарага", "аренду",
    ],
    "utilities": [
        "коммуналка", "свет", "вода", "электричество", "за газ", "kommunal", "komunal", "svet",
        "gaz", "elektr", "elektrga", "suv", "issiq suv", "tok", "kommunalka", "kommunal to'lov",
        "kvartplata", "musor", "chiqindi", "elektr energiya", "elektr energiyasi", "isitish",
        "otopleniye", "kommunalga", "коммунал", "сув", "ток", "мусор", "квартплата", "электр",
    ],
    "telecom_internet": [
        "интернет", "связь", "симкарта", "билайн", "юсел", "узтелеком", "вайфай", "вай-фай",
        "internet", "aloqa", "telefon", "tarifga", "tarif", "wifi", "wi-fi", "uztelekom",
        "beeline", "bilayn", "yusel", "ucel", "ucell", "mobiuz", "uzmobile", "uztelecom",
        "humans", "mobil aloqa", "mobil", "internet paket", "paket", "trafik", "simka",
        "sim karta", "telefonga", "aloqaga", "internetga", "алоқа", "телефон", "мобил",
        "мобиуз", "тариф", "симка", "пакет",
    ],
    "repairs_furnishing": [
        "ремонт", "мебель", "стройматериалы", "stroymaterial", "remont", "rezetka",
        "vklyuchatel", "ta'mir", "mebel", "tamir", "tamirlash", "ta'mirlash", "ta'miri",
        "tamiri", "santexnik", "santexnika", "oboy", "kafel", "plitka", "bo'yoq", "kraska",
        "sement", "g'isht", "qurilish", "qurilish mollalari", "usta", "elektrik", "jihoz",
        "jihozlash", "divan", "shkaf", "таъмир", "таъмирлаш", "тамир", "қурилиш", "уста",
        "жиҳоз", "сантехник", "обои", "строительные материалы",
    ],
    "children": [
        "дети", "bolalar", "bola", "bolalarga", "farzand", "farzandlar", "бола", "болалар",
        "фарзанд", "ребёнок", "ребенок",
    ],
    "kindergarten_school": [
        "садик", "школа", "детский сад", "bog'cha", "bogcha", "maytab", "inst", "univer",
        "maktab", "bog'chaga", "bogchaga", "maktabga", "kontrakt", "kontrakt to'lovi", "litsey",
        "litseyga", "universitet", "institut", "kollej", "o'quv", "боғча", "мактаб", "контракт",
        "лицей", "университет", "институт", "колледж",
    ],
    "clubs_tutoring": [
        "кружок", "репетитор", "to'garak", "repetitor", "kurs", "kurslar", "kursga", "dars",
        "darslar", "ustoz", "ustozga", "to'garakka", "to'garaklar", "tutor", "курс", "курсы",
        "кружки", "тўгарак", "устоз", "дарс",
    ],
    "kids_goods": [
        "игрушки", "детская одежда", "подгузники", "bolalar buyumlari", "o'yinchoq", "oyinchoq",
        "o'yinchoqlar", "oyinchoqlar", "pampers", "podguzniklar", "bolalar kiyimi",
        "bolalar kiyim", "kolyaska", "sut aralashmasi", "smes", "ўйинчоқ", "памперс", "коляска",
        "смесь", "болалар кийими",
    ],
    "health": [
        "здоровье", "salomatlik", "sogliq", "sog'liq", "davolanish", "davolash", "davolanishga",
        "lechenie", "саломатлик", "соғлиқ", "даволаниш", "лечение",
    ],
    "pharmacy": [
        "лекарства", "аптека", "таблетки", "dori", "dori-darmon", "apteka", "dorixona",
        "dorilar", "dori darmon", "vitamin", "vitaminlar", "tabletka", "tabletkalar",
        "antibiotik", "дорихона", "дори", "дорилар", "таблетка", "витамины",
    ],
    "doctors_clinics": [
        "врач", "клиника", "больница", "анализы", "shifokor", "doxtr", "lorga", "lo'rga",
        "klinika", "vrach", "vrachga", "doktor", "doktorga", "shifokorga", "shifoxona",
        "kasalxona", "poliklinika", "analiz", "tahlil", "tahlillar", "uzi", "tekshiruv",
        "kardiolog", "nevropatolog", "ginekolog", "terapevt", "pediatr", "okulist", "lor",
        "rentgen", "mrt", "шифокор", "докторга", "касалхона", "поликлиника", "анализ", "тахлил",
        "узи", "текширув",
    ],
    "dentistry": [
        "стоматолог", "зубы", "дантист", "stomatolog", "tish", "tishchi", "tish doktor",
        "tish shifokori", "tish davolash", "stomatologiya", "stomatologga", "plomba", "tishga",
        "стоматология", "стоматологга", "тиш", "тишчи", "зуб", "пломба",
    ],
    "events_celebrations": [
        "мероприятие", "днюха", "день раждение", "корпоратив", "korporativ", "tadbir",
        "tug'ilgan kun", "tugilgan kun", "tug'ilgan kunga", "tavallud", "bayram", "bayramga",
        "yubiley", "ziyofat", "bazm", "tabrik", "туғилган кун", "тадбир", "байрам", "базм",
        "юбилей",
    ],
    "toi_celebrations": [
        "той", "маърака", "свадьба", "юбилей", "to'y", "toy", "navkar", "marosim", "to'yga",
        "toyga", "to'yda", "to'y xarajati", "nikoh", "nikohga", "beshik to'y", "beshik toy",
        "sunnat", "sunnat to'y", "hayit to'y", "aqiqa", "ma'raka", "maraka", "marosimga",
        "kelin salom", "qiz uzatish", "tuy", "тўй", "тўйга", "никоҳ", "никох", "суннат",
        "маъракa", "мароcим",
    ],
    "event_gifts": [
        "подарок на той", "цветы", "sovg'a", "podarka", "sovga", "sovg'alar", "sovg'aga",
        "guldasta", "gul", "gullar", "podarok", "tuhfa", "совға", "совга", "гул", "гуллар",
        "гулдаста",
    ],
    "shopping_leisure": [
        "покупки", "xarid", "xaridlar", "xaridga", "xarid qildim", "savdo", "shopping",
        "shoping", "покупка", "харид",
    ],
    "clothing": [
        "одежда", "обувь", "кроссовки", "kiyim", "oyo kiyim", "krasovka", "krasopka",
        "poyabzal", "kiyim-kechak", "kiyim kechak", "kiyimlar", "kiyimga", "oyoq kiyim",
        "oyoq kiyimi", "krossovka", "krossovkalar", "tufli", "ko'ylak", "koylak", "shim",
        "kurtka", "palto", "bosh kiyim", "ichki kiyim", "paypoq", "etik", "botinka", "jinsi",
        "кийим", "оёқ кийим", "кроссовка", "этик", "туфли", "куртка", "ботинки", "джинсы",
        "кўйлак", "шим",
    ],
    "entertainment": [
        "кино", "боулинг", "развлечения", "kino", "ko'ngilochar", "кайфовал", "kaypga",
        "ko'ngil ochar", "kinoga", "kinoteatr", "teatr", "teatrga", "sirk", "akvapark",
        "aquapark", "attraksion", "attraksionlar", "karaoke", "bouling", "bowling",
        "playstation", "ps5", "dam olish", "istirohat", "konsert", "konsertga", "muzey",
        "zoopark", "кинога", "кинотеатр", "театр", "театрга", "цирк", "аквапарк", "концерт",
        "музей", "караоке", "ўйин", "кўнгилочар", "дам олиш", "развлечение",
    ],
    "subscriptions": [
        "подписка", "netflix", "spotify", "obuna", "netkaga", "cs2", "КС2", "комп", "dota",
        "dota 2", "obunaga", "obuna to'lovi", "oylik obuna", "podpiska", "youtube premium",
        "youtube", "yt premium", "apple music", "icloud", "chatgpt", "telegram premium",
        "premium", "okko", "kinopoisk", "ivi", "wink", "google one", "app store", "appstore",
        "play market", "playmarket", "подписку", "подписки", "обуна", "спотифай", "нетфликс",
        "премиум",
    ],
    "beauty_care": [
        "салон красоты", "парикмахерская", "косметика", "сартарош", "go'zallik saloni",
        "satarosh", "sartarosh", "sartaroshxona", "sartaroshga", "soch olish", "soch oldirish",
        "pardoz", "pardoz-andoz", "kosmetika", "kosmetik", "manikyur", "pedikyur", "massaj",
        "spa", "salon", "go'zallik", "gozallik", "barber", "barbershop", "parikmaxer",
        "parikmaher", "atir", "parfyum", "shampun", "krem", "парикмахер", "маникюр", "педикюр",
        "массаж", "барбер", "салон", "сартарошхона", "сартарошга", "соч олиш", "атир", "парфюм",
    ],
    "salary": [
        "зарплата", "зп", "аванс", "оклад", "maosh", "ish haqi", "oylik", "oyli", "oylik maosh",
        "oyligim", "avans", "avans pul", "maoshim", "ish haqim", "premiya", "mukofot", "bonus",
        "иш ҳақи", "маош", "ойлик", "премия", "бонус",
    ],
    "side_job": [
        "подработка", "фриланс", "шабашка", "qo'shimcha ish", "leviy ish", "leviy",
        "podrabotka", "frilans", "freelance", "shabashka", "qo'shimcha daromad",
        "qoshimcha ish", "qo'shimcha ishdan", "buyurtma", "zakaz", "zakazdan", "ishlab topdim",
        "bir kunlik ish", "қўшимча иш", "фрилансер", "заказ", "ишлаб топдим",
    ],
    "gifts": [
        "подарили", "подарок получил", "sovg'a oldim", "podarka", "oyincho", "sovg'a berishdi",
        "sovga oldim", "sovga berdi", "sovg'a qilishdi", "sovg'a qildi", "salomlik",
        "salomlik puli", "tabrik puli", "bayram puli", "bayramlik", "hayitlik", "hayitlik puli",
        "совға олдим", "совга олдим", "ҳайитлик", "байрамлик", "саломлик",
    ],
    "family_transfers": [
        "перевод от родителей", "от родных", "от мамы", "от папы", "qarindoshdan pul",
        "ota-onadan", "ota onadan", "ota-onamdan", "onamdan", "dadamdan", "otamdan", "akamdan",
        "opamdan", "singlimdan", "ukamdan", "akamdan pul", "onamdan pul", "dadamdan pul",
        "qarindoshdan", "qarindoshlardan", "yaqinlardan", "oilamdan", "ota-onam yubordi",
        "onam yubordi", "dadam yubordi", "онамдан", "отамдан", "дадамдан", "акамдан", "опамдан",
        "қариндошдан", "ота-онамдан",
    ],
}

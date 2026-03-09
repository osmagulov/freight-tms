TRANSLATIONS = {
    "ru": {
        "welcome_back": "👋 Здравствуйте, {name}!",
        "welcome_new": "👋 Здравствуйте! Я помощник диспетчера.\nПожалуйста, выберите язык / Тілді таңдаңыз:",
        "ask_name": "✍️ Напишите ваши Имя и Фамилию:",
        "btn_phone": "📱 Отправить мой номер",
        "ask_phone": "👍 Хорошо, {name}. Теперь нажмите на выделенную кнопку внизу экрана, чтобы отправить свой номер телефона.",
        "ask_vehicle": "🚚 Напишите гос. номер вашей машины (например: 123 ABC 01):",
        "reg_success": "✅ Вы успешно зарегистрированы!\nИмя: {name}\nМашина: {plate}\n\n👇 Нажимайте на кнопки внизу для работы.",
        "reg_cancelled": "❌ Отменено. Нажмите /start чтобы начать заново.",
        "need_reg": "⚠️ Нажмите /start для регистрации.",
        
        # Phase 3: dispatcher-first trip opening flow (TRIP-03)
        "open_trip_no_planned": "⚠️ У вас нет назначенного рейса. Обратитесь к диспетчеру.",
        "open_trip_confirm_details": (
            "📋 Ваш рейс:\n"
            "🗺 Маршрут: {route}\n"
            "📦 Груз: {cargo}\n"
            "🏢 Клиент: {client}\n"
            "🕐 Плановое отправление: {departure}\n\n"
            "Подтверждаете отправление?"
        ),
        "open_trip_confirm_prompt": "Нажмите Да или Нет.",
        "btn_yes": "Да",
        "btn_no": "Нет",
        "open_trip_ask_odo": "🔢 Напишите пробег машины СЕЙЧАС (только цифры):",
        "open_trip_odo_error": "⚠️ Напишите ТОЛЬКО ЦИФРЫ (без букв).",
        "open_trip_activate_error": "⚠️ Не удалось активировать рейс. Попробуйте снова или обратитесь к диспетчеру.",
        "open_trip_success": "✅ Рейс активирован! Счастливой дороги!\nМаршрут: {route}\nНачальный пробег: {odometer} км.\n\n👇 Не забывайте добавлять расходы внизу экрана.",
        "open_trip_cancelled": "❌ Действие отменено.",

        # Legacy keys kept for backward compatibility (not used in new flow)
        "open_trip_ask_route": "📍 Напишите откуда и куда вы едете (например: Алматы - Москва):",
        "open_trip_ask_cargo": "🚚 Напишите ГОС. НОМЕР машины и прицепа на которых вы едете (например: 123 ABC 01):",
        "open_trip_ask_docs": "📸 Сфотографируйте накладную (CMR) и отправьте фото:",
        "open_trip_docs_error": "⚠️ Отправьте именно ФОТО документа.",
        
        "exp_no_trip": "У вас нет активного рейса. Сначала откройте рейс (/open_trip).",
        "exp_no_trip": "⚠️ Вы не в рейсе. Сначала нажмите '🚚 Открыть рейс'.",
        "exp_ask_type": "Какую трату вы хотите добавить?",
        "exp_type_fuel": "⛽ Заправил топливо",
        "exp_type_diem": "🍔 Еда (суточные)",
        "exp_type_fine": "👮 Заплатил штраф",
        "exp_type_repair": "🔧 Починил машину",
        "exp_type_other": "📦 Другое",
        "exp_ask_amount": "🔢 Напишите потраченную СУММУ (только цифры):",
        "exp_ask_currency": "💵 В какой валюте платили?",
        "exp_ask_photo": "📸 Отправьте ФОТО ЧЕКА (или нажмите /skip_photo если чека нет):",
        "exp_ask_card_photo": "💳 Теперь отправьте ФОТО КАРТЫ или ТЕРМИНАЛА, с которых была оплата (или нажмите /skip_card если платили наличными):",
        "exp_ask_comment": "✍️ Напишите комментарий (за что заплатили) или нажмите /skip_comment:",
        "exp_success": "✅ Сохранено: {type} на {amount} {currency}!",
        "exp_cancelled": "❌ Действие отменено.",
        
        "menu_open_trip": "🚚 НАЧАТЬ РЕЙС",
        "menu_add_expense": "💸 ДОБАВИТЬ РАСХОД",
        "menu_share_location": "📍 ОТПРАВИТЬ ГЕОЛОКАЦИЮ",
        
        "loc_ask": "👇 Нажмите на БОЛЬШУЮ КНОПКУ внизу чтобы отправить где вы сейчас находитесь.",
        "loc_btn": "📍 ОТПРАВИТЬ МОЮ ГЕОЛОКАЦИЮ",
        "loc_success": "✅ Геопозиция получена. Спасибо!",
        "loc_error": "⚠️ Нажмите на кнопку внизу экрана.",
        
        "menu_close_trip": "🏁 ЗАВЕРШИТЬ РЕЙС",
        "close_trip_no_trip": "⚠️ У вас нет открытого рейса.",
        "close_trip_ask_odo": "🔢 Рейс завершен. Напишите пробег машины СЕЙЧАС (только цифры):",
        "close_trip_odo_error": "⚠️ Ошибка. Пробег должен быть больше начального и состоять только из цифр.",
        "close_trip_ask_doc": "📸 Сфотографируйте закрывающую накладную (CMR) и отправьте фото:",
        "close_trip_doc_error": "⚠️ Отправьте именно ФОТО документа.",
        "close_trip_success": "✅ Рейс завершен!\nВы проехали: {diff} км.\nЖдем вас на новых маршрутах!",
        "close_trip_cancelled": "❌ Действие отменено.",

        # Fuel flow strings
        "exp_ask_liters": "Сколько литров заправили? (введите число)",
        "exp_ask_odometer": "Введите текущие показания одометра (км):",
        "exp_odo_too_low": "Одометр должен быть больше предыдущего ({last} км). Введите снова:",
        "exp_odo_too_high": "Одометр слишком большой (разница более 5000 км). Проверьте показания и введите снова:",
        "exp_odo_error": "Неверный формат. Введите целое число (км):",
        "exp_ask_station": "Название заправочной станции:",
        "exp_ask_city": "Город (для суточных):",
        "exp_ask_reason": "Укажите причину/категорию (например: ремонт тормозов, штраф за скорость):",
        "exp_ask_subcategory": "Категория расхода (ремонт / запчасти / паром / таможня / другое):",
        "exp_duplicate": "Такой расход уже зафиксирован в эту минуту. Если это ошибка, подождите минуту и попробуйте снова.",

        # EXP-06: expense summary strings
        "exp_summary_header": "Расходы по текущему рейсу:",
        "exp_summary_line": "{status}: {count} поз. / {total:.0f} KZT",
        "exp_summary_total": "ИТОГО одобрено: {total:.0f} KZT",
        "exp_summary_empty": "По этому рейсу расходов пока нет.",
    },
    "kk": {
        "welcome_back": "👋 Сәлеметсіз бе, {name}!",
        "welcome_new": "👋 Сәлеметсіз бе! Мен диспетчердің көмекшісімін.\nПожалуйста, выберите язык / Тілді таңдаңыз:",
        "ask_name": "✍️ Толық аты-жөніңізді жазыңыз:",
        "btn_phone": "📱 Өз нөмірімді жіберу",
        "ask_phone": "👍 Жақсы, {name}. Енді телефон нөміріңізді жіберу үшін экранның астындағы батырманы басыңыз.",
        "ask_vehicle": "🚚 Көлігіңіздің мемлекеттік нөмірін жазыңыз (мысалы: 123 ABC 01):",
        "reg_success": "✅ Сіз сәтті тіркелдіңіз!\nАты-жөні: {name}\nКөлік: {plate}\n\n👇 Жұмысты бастау үшін төмендегі батырмаларды басыңыз.",
        "reg_cancelled": "❌ Тоқтатылды. Қайта бастау үшін /start басыңыз.",
        "need_reg": "⚠️ Тіркелу үшін /start басыңыз.",
        
        # Phase 3: dispatcher-first trip opening flow (TRIP-03)
        "open_trip_no_planned": "⚠️ Сізге тағайындалған рейс жоқ. Диспетчерге хабарласыңыз.",
        "open_trip_confirm_details": (
            "📋 Сіздің рейсіңіз:\n"
            "🗺 Маршрут: {route}\n"
            "📦 Жүк: {cargo}\n"
            "🏢 Клиент: {client}\n"
            "🕐 Жоспарлы жөнелту: {departure}\n\n"
            "Жөнелтуді растайсыз ба?"
        ),
        "open_trip_confirm_prompt": "Иә немесе Жоқ батырмасын басыңыз.",
        "btn_yes": "Иә",
        "btn_no": "Жоқ",
        "open_trip_ask_odo": "🔢 Көліктің ҚАЗІРГІ жүрісін жазыңыз (тек сандар):",
        "open_trip_odo_error": "⚠️ ТЕК САНДАРДЫ жазыңыз (әріптерсіз).",
        "open_trip_activate_error": "⚠️ Рейсті белсендіру мүмкін болмады. Қайта көріңіз немесе диспетчерге хабарласыңыз.",
        "open_trip_success": "✅ Рейс белсендірілді! Сәт сапар!\nМаршрут: {route}\nБастапқы жүріс: {odometer} км.\n\n👇 Экранның астындағы шығындарды қосуды ұмытпаңыз.",
        "open_trip_cancelled": "❌ Әрекет тоқтатылды.",

        # Legacy keys kept for backward compatibility (not used in new flow)
        "open_trip_ask_route": "📍 Қайдан және қайда бара жатқаныңызды жазыңыз (мысалы: Алматы - Мәскеу):",
        "open_trip_ask_cargo": "🚚 Көліктің немесе тіркеменің МЕМЛЕКЕТТІК НӨМІРІН жазыңыз (мысалы: 123 ABC 01):",
        "open_trip_ask_docs": "📸 Жүкқұжатты (CMR) суретке түсіріп, жіберіңіз:",
        "open_trip_docs_error": "⚠️ Міндетті түрде құжаттың СУРЕТІН жіберіңіз.",

        "exp_no_trip": "⚠️ Сіз рейсте емессіз. Алдымен '🚚 РЕЙСТІ БАСТАУ' батырмасын басыңыз.",
        "exp_ask_type": "Қандай шығын қосасыз?",
        "exp_type_fuel": "⛽ Жанармай құйдым",
        "exp_type_diem": "🍔 Тамақ (тәуліктік)",
        "exp_type_fine": "👮 Айыппұл төледім",
        "exp_type_repair": "🔧 Көлікті жөндедім",
        "exp_type_other": "📦 Басқа",
        "exp_ask_amount": "🔢 Жұмсалған СОМАНЫ жазыңыз (тек сандар):",
        "exp_ask_currency": "💵 Қандай валютада төледіңіз?",
        "exp_ask_photo": "📸 ЧЕКТІҢ СУРЕТІН жіберіңіз (немесе чек жоқ болса /skip_photo басыңыз):",
        "exp_ask_card_photo": "💳 Енді төленген КАРТАНЫҢ немесе ТЕРМИНАЛДЫҢ СУРЕТІН жіберіңіз (қолма-қол төлесеңіз /skip_card басыңыз):",
        "exp_ask_comment": "✍️ Комментарий жазыңыз (не үшін төледіңіз) немесе /skip_comment басыңыз:",
        "exp_success": "✅ Сақталды: {type} - {amount} {currency}!",
        "exp_cancelled": "❌ Әрекет тоқтатылды.",

        "menu_open_trip": "🚚 РЕЙСТІ БАСТАУ",
        "menu_add_expense": "💸 ШЫҒЫН ҚОСУ",
        "menu_share_location": "📍 ГЕОЛОКАЦИЯ ЖІБЕРУ",
        
        "loc_ask": "👇 Қазір қайда екеніңізді жіберу үшін астындағы ҮЛКЕН БАТЫРМАНЫ басыңыз.",
        "loc_btn": "📍 МЕНІҢ ГЕОЛОКАЦИЯМДЫ ЖІБЕРУ",
        "loc_success": "✅ Геопозиция қабылданды. Рақмет!",
        "loc_error": "⚠️ Экранның астындағы батырманы басыңыз.",
        
        "menu_close_trip": "🏁 РЕЙСТІ АЯҚТАУ",
        "close_trip_no_trip": "⚠️ Сізде ашық рейс жоқ.",
        "close_trip_ask_odo": "🔢 Рейс аяқталды. Көліктің ҚАЗІРГІ жүрісін жазыңыз (тек сандар):",
        "close_trip_odo_error": "⚠️ Қате. Жүріс бастапқыдан көп болуы керек және тек сандардан тұруы керек.",
        "close_trip_ask_doc": "📸 Жабылатын жүкқұжатты (CMR) суретке түсіріп, жіберіңіз:",
        "close_trip_doc_error": "⚠️ Міндетті түрде құжаттың СУРЕТІН жіберіңіз.",
        "close_trip_success": "✅ Рейс аяқталды!\nСіздің жүріп өткен жолыңыз: {diff} км.\nЖаңа маршруттарда күтеміз!",
        "close_trip_cancelled": "❌ Әрекет тоқтатылды.",

        # Fuel flow strings
        "exp_ask_liters": "Қанша литр құйдыңыз? (санды енгізіңіз)",
        "exp_ask_odometer": "Ағымдағы одометр көрсеткішін енгізіңіз (км):",
        "exp_odo_too_low": "Одометр алдыңғы мәннен ({last} км) үлкен болуы керек. Қайта енгізіңіз:",
        "exp_odo_too_high": "Одометр тым үлкен (айырмашылық 5000 км-ден астам). Тексеріп, қайта енгізіңіз:",
        "exp_odo_error": "Дұрыс емес формат. Бүтін санды енгізіңіз (км):",
        "exp_ask_station": "Жанармай бекетінің атауы:",
        "exp_ask_city": "Қала (тәуліктік үшін):",
        "exp_ask_reason": "Себепті/санатты көрсетіңіз (мысалы: тежегіш жөндеу, жылдамдық айыбы):",
        "exp_ask_subcategory": "Шығын санаты (жөндеу / бөлшек / паром / кеден / басқа):",
        "exp_duplicate": "Бұл шығын осы минутта жазылды. Егер бұл қате болса, бір минут күтіп, қайта көріңіз.",

        # EXP-06: expense summary strings
        "exp_summary_header": "Ағымдағы рейс бойынша шығындар:",
        "exp_summary_line": "{status}: {count} поз. / {total:.0f} KZT",
        "exp_summary_total": "БАРЛЫҒЫ бекітілді: {total:.0f} KZT",
        "exp_summary_empty": "Бұл рейс бойынша шығындар жоқ.",
    }
}

def get_text(lang: str, key: str, **kwargs) -> str:
    # Default to ru if lang not found
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])
    text = lang_dict.get(key, TRANSLATIONS["ru"].get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text

def get_main_menu(lang: str, has_active_trip: bool = False):
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    keyboard = []
    if has_active_trip:
        keyboard.append([KeyboardButton(get_text(lang, "menu_add_expense")), KeyboardButton(get_text(lang, "menu_close_trip"))])
        keyboard.append([KeyboardButton(get_text(lang, "menu_share_location"))])
    else:
        keyboard.append([KeyboardButton(get_text(lang, "menu_open_trip"))])
        
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

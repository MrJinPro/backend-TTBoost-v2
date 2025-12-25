const String kApiBaseUrl = String.fromEnvironment(
	'API_BASE_URL',
	defaultValue: 'https://api.ttboost.pro',
);

const String kMediaBaseUrl = String.fromEnvironment(
	'MEDIA_BASE_URL',
	defaultValue: 'https://media.ttboost.pro',
);

const String kWebSocketUrl = String.fromEnvironment(
	'WS_URL',
	defaultValue: 'wss://api.ttboost.pro/v2/ws',
);

// In-app subscriptions product IDs (configure per build).
const String kAndroidProductOne = String.fromEnvironment(
	'ANDROID_PRODUCT_ONE',
	defaultValue: 'nova_one_mobile',
);

const String kAndroidProductDuo = String.fromEnvironment(
	'ANDROID_PRODUCT_DUO',
	defaultValue: 'nova_duo',
);

const String kIosProductOne = String.fromEnvironment(
	'IOS_PRODUCT_ONE',
	defaultValue: 'nova_one_mobile',
);

const String kIosProductDuo = String.fromEnvironment(
	'IOS_PRODUCT_DUO',
	defaultValue: 'nova_duo',
);

// Максимальный размер загружаемого звука (1 MiB)
const int kMaxSoundUploadBytes = 1024 * 1024;

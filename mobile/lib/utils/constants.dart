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
// Legacy naming: monthly/yearly. Defaults map to current product ids.
const String kAndroidProductMonthly = String.fromEnvironment(
	'ANDROID_PRODUCT_MONTHLY',
	defaultValue: kAndroidProductOne,
);

const String kAndroidProductYearly = String.fromEnvironment(
	'ANDROID_PRODUCT_YEARLY',
	defaultValue: kAndroidProductDuo,
);

const String kIosProductMonthly = String.fromEnvironment(
	'IOS_PRODUCT_MONTHLY',
	defaultValue: kIosProductOne,
);

const String kIosProductYearly = String.fromEnvironment(
	'IOS_PRODUCT_YEARLY',
	defaultValue: kIosProductDuo,
);

// Google Play subscriptions: base plan / offer ids (optional)
const String kAndroidMonthlyBasePlanId = String.fromEnvironment(
	'ANDROID_MONTHLY_BASE_PLAN_ID',
	defaultValue: '',
);

const String kAndroidMonthlyOfferId = String.fromEnvironment(
	'ANDROID_MONTHLY_OFFER_ID',
	defaultValue: '',
);

const String kAndroidYearlyBasePlanId = String.fromEnvironment(
	'ANDROID_YEARLY_BASE_PLAN_ID',
	defaultValue: '',
);

const String kAndroidYearlyOfferId = String.fromEnvironment(
	'ANDROID_YEARLY_OFFER_ID',
	defaultValue: '',
);

const String kAndroidPackageName = String.fromEnvironment(
	'ANDROID_PACKAGE_NAME',
	defaultValue: 'com.mrjinpro.novaboostmobile',
);

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

// Spotify OAuth (PKCE)
// Configure via: flutter run --dart-define=SPOTIFY_CLIENT_ID=... 
// Redirect URI must match AndroidManifest intent-filter.
const String kSpotifyClientId = String.fromEnvironment(
	'SPOTIFY_CLIENT_ID',
	defaultValue: '',
);

// Default redirect for Android: novaboost://spotify-auth
const String kSpotifyRedirectUri = String.fromEnvironment(
	'SPOTIFY_REDIRECT_URI',
	defaultValue: 'novaboost://spotify-auth',
);

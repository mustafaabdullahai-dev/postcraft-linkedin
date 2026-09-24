export interface ValidationResult {
  valid: boolean;
  quality_score: number;
  issues: string[];
  suggestions: string[];
}

export interface User {
  user_id: string;
  name: string;
  headline: string;
  picture_url: string;
  email: string;
  is_guest: boolean;
  connected: boolean;
  created_at: string;
}

export interface PostRecord {
  record_id: string;
  user_query: string;
  owner_id: string;

  topic: string;
  audience: string;
  content_angle: string;

  priority: string;
  post_type: string;
  language: string;

  generated_post: string;
  final_post: string | null;
  hashtags: string[];
  image_prompt: string;
  image_url: string | null;
  image_provider: string;
  text_model: string;
  validation_status: string;
  validation_result: ValidationResult;
  review_status: string;
  approval_status: string;
  generation_status: string;
  publishing_status: string;
  google_sheet_status: string;
  linkedin_post_id: string | null;
  record_status: string;
  scheduled_at: string | null;
  published_at: string | null;
  analytics: EngagementStats;
  voice_profile_id: string | null;
  voice_profile_name: string;
  created_at: string;
  updated_at: string;
  error: string | null;
  history: Array<{ event: string; at: string }>;
}

export interface EngagementStats {
  likes: number;
  comments: number;
  shares: number;
  impressions: number;
  source?: string;
  fetched_at?: string | null;
}

export interface StatusCounts {
  total: number;
  ready_for_review: number;
  scheduled: number;
  published: number;
  failed: number;
}

export interface PostListResponse {
  items: PostRecord[];
  counts: StatusCounts;
  total: number;
}

export interface HealthInfo {
  status: string;
  environment: string;
  text_provider: string;
  image_provider: string;
  linkedin_mode: string;
  sheets_mode: string;
  linkedin_configured: boolean;
}

export interface PostFilters {
  priority?: string;
  post_type?: string;
  status?: string;
  q?: string;
  sort?: string;
  from_date?: string;
  to_date?: string;
}

export interface VoiceProfile {
  voice_id: string;
  name: string;
  description: string;
  tone: string;
  audience: string;
  word_target: number;
  emojis: boolean | null;
  bullets: boolean | null;
  short_paragraphs: boolean | null;
  practitioner_story: boolean | null;
  discussion_cta: boolean | null;
  is_default: boolean;
}

export interface SuggestResponse {
  original: string;
  improved: string;
  note: string;
}

export interface PostEditSuggestions {
  summary: string;
  notes: string[];
  improved_draft: string;
}

export interface FormattingPrefs {
  emojis: boolean;
  bullets: boolean;
  bold_keywords: boolean;
  short_paragraphs: boolean;
  practitioner_story: boolean;
  discussion_cta: boolean;
  /** Target length in words (hook+body+CTA, hashtags excluded). 0 = auto. */
  word_target: number;
}

export const DEFAULT_FORMATTING: FormattingPrefs = {
  emojis: true,
  bullets: true,
  bold_keywords: true,
  short_paragraphs: true,
  practitioner_story: false,
  discussion_cta: true,
  word_target: 0,
};

export const POST_LENGTH_OPTIONS = [
  { value: 0, label: "Auto" },
  { value: 90, label: "Short (~90 words)" },
  { value: 150, label: "Medium (~150 words)" },
  { value: 250, label: "Long (~250 words)" },
  { value: -1, label: "Custom words…" },
] as const;

export const FORMATTING_OPTIONS: Array<{ key: keyof FormattingPrefs; label: string; hint: string }> = [
  { key: "emojis", label: "Emojis", hint: "3-7 natural emojis in every post type" },
  { key: "bullets", label: "Bullets", hint: "• lists for takeaways" },
  { key: "bold_keywords", label: "Bold key terms", hint: "**bold** the important words" },
  { key: "short_paragraphs", label: "Short paragraphs", hint: "1-3 sentences, scannable" },
  { key: "practitioner_story", label: "Practitioner story", hint: "Field perspective / example" },
  { key: "discussion_cta", label: "Discussion CTA", hint: "End with a contextual question" },
];

export const PRIORITIES = ["High", "Medium", "Low"] as const;

export const POST_TYPES = [
  "How-To",
  "Thought Leadership",
  "Insights",
  "News",
  "Motivational",
  "Promotional",
] as const;

// Quick "tabs" for the language selector — any language can also be typed freely
// so post + image text work for users in every locale.
export const LANGUAGE_TABS = [
  "English",
  "العربية",
  "中文",
  "Español",
  "Français",
  "हिन्दी",
  "Português",
  "Deutsch",
  "日本語",
] as const;

// 100+ languages (native names, with English name where the native script is
// non-Latin so users can search in either). Searchable + freely typeable.
export const LANGUAGES = [
  "English",
  "English (UK)",
  "English (Australia)",
  "Español",
  "Español (LATAM)",
  "Français",
  "Français (Canada)",
  "Deutsch",
  "Português",
  "Português (Brasil)",
  "Italiano",
  "Nederlands",
  "Vlaams",
  "العربية",
  "中文（简体）",
  "中文（繁體）",
  "हिन्दी",
  "日本語",
  "한국어",
  "বাংলা",
  "اردو",
  "עברית",
  "فارسی",
  "Türkçe",
  "Polski",
  "Русский",
  "Українська",
  "Ελληνικά",
  "Svenska",
  "Dansk",
  "Norsk",
  "Suomi",
  "Čeština",
  "Slovenčina",
  "Magyar",
  "Română",
  "Български",
  "Српски",
  "Hrvatski",
  "Slovenščina",
  "Bosanski",
  "Македонски",
  "Shqip",
  "Lietuvių",
  "Latviešu",
  "Eesti",
  "Íslenska (Icelandic)",
  "Gaeilge (Irish)",
  "Gàidhlig (Scottish Gaelic)",
  "Cymraeg (Welsh)",
  "Malti (Maltese)",
  "Català (Catalan)",
  "Euskara (Basque)",
  "Galego (Galician)",
  "Occitan",
  "Brezhoneg (Breton)",
  "Lëtzebuergesch (Luxembourgish)",
  "Frysk (Frisian)",
  "Հայերեն (Armenian)",
  "ქართული (Georgian)",
  "Azərbaycanca (Azerbaijani)",
  "Қазақша (Kazakh)",
  "Oʻzbekcha (Uzbek)",
  "Кыргызча (Kyrgyz)",
  "Тоҷикӣ (Tajik)",
  "Türkmençe (Turkmen)",
  "Монгол хэл (Mongolian)",
  "Kurdî (Kurdish)",
  "پښتو (Pashto)",
  "Dari",
  "سنڌي (Sindhi)",
  "नेपाली (Nepali)",
  "සිංහල (Sinhala)",
  "தமிழ் (Tamil)",
  "తెలుగు (Telugu)",
  "ಕನ್ನಡ (Kannada)",
  "മലയാളം (Malayalam)",
  "मराठी (Marathi)",
  "ગુજરાતી (Gujarati)",
  "ਪੰਜਾਬੀ (Punjabi)",
  "ଓଡ଼ିଆ (Odia)",
  "অসমীয়া (Assamese)",
  "Bahasa Melayu (Malay)",
  "Bahasa Indonesia (Indonesian)",
  "Filipino (Tagalog)",
  "Cebuano",
  "Kapampangan",
  "ไทย (Thai)",
  "Tiếng Việt (Vietnamese)",
  "ខ្មែរ (Khmer)",
  "ລາວ (Lao)",
  "မြန်မာ (Burmese)",
  "Jawa (Javanese)",
  "Sunda (Sundanese)",
  "Kiswahili (Swahili)",
  "አማርኛ (Amharic)",
  "Soomaali (Somali)",
  "Hausa",
  "Yorùbá",
  "Igbo",
  "isiZulu (Zulu)",
  "isiXhosa (Xhosa)",
  "Afrikaans",
  "Shona",
  "Sesotho",
  "Twi (Akan)",
  "Kinyarwanda",
  "Ganda (Luganda)",
  "Lingala",
  "Gĩkũyũ (Kikuyu)",
  "ትግርኛ (Tigrinya)",
  "Afaan Oromoo (Oromo)",
  "Malagasy",
  "Fula (Fulani)",
  "Wolof",
  "Bambara",
  "Chichewa (Nyanja)",
  "Kiswahili (Kongo)",
  "Māori (Maori)",
  "ʻŌlelo Hawaiʻi (Hawaiian)",
  "Sāmoa (Samoan)",
  "Lea Faka-Tonga (Tongan)",
  "Fijian",
  "Reo Tahiti (Tahitian)",
  "guarani",
] as const;
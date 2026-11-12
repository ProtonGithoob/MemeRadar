# Ultra-Early Detection səhifəsi — arxitektura auditi (2026-11-12)

Əhatə: yalnız `/ultra-early` səhifəsi və onu qidalandıran zəncir
(worker → early runtime → stage snapshot → `list_early_radar` → API → web).
Mənbə: kod oxunuşu və real mainnet məlumatı ilə işlədilmiş lokal worker bazası
(71 namizəd, 397 token metadata oxunuşu). "✔" işarəsi kodda və ya məlumatda
təsdiqləndiyini göstərir.

## 1. Qısa cavab: bu səhifədən "almalıyam" qərarını çıxarmaq olarmı?

**Hazırda yox.** Səhifənin "al" deməyə ən yaxın siqnalı `ALERT READY` qapısı və
`ENTRY_READY` state-idir, amma hər ikisi canlı rejimdə **konstruksiyaya görə
əlçatmazdır** (§2). Ölçülmüş real işləmədə 71 namizəddən 0-ı PASS aldı,
maksimum `early_score` 0 oldu, alert növbəsinə 0 siqnal düşdü.

Bundan əlavə, sistemin siqnallarının sonradan qazandırıb-qazandırmadığı
ölçülməyib (`REAL_WORLD_ALPHA_NOT_YET_PROVEN`). Yəni qapılar açılsa belə,
`ALERT READY` "bu token bütün təhlükəsizlik və momentum yoxlamalarından keçdi"
deməkdir, "qazanacaq" demək deyil.

## 2. Niyə heç bir token alert həddinə çatmır (P0)

| # | Tapıntı | Sübut |
| --- | --- | --- |
| A1 ✔ | **Skor tavanı ~60-dır.** Skorun 30%-i (`WalletQuality` 0.20, `SmartMoneyConfluence` 0.05, `SocialCorroboration` 0.05) üçün canlı məlumat mənbəyi yoxdur: worker heç yerdə `raw_smart_wallet_count` vermir. Mükəmməl halda (organic=100, momentum=100, safety=PASS) skor 25+20+15+10 = 70, natamam-sübut cəzası −10 ilə **60** olur. Real halda (organic ≈ 65, momentum ≈ 50) ≈ 46, yəni WATCH. | `early_scoring.py:27-36`, `:153`; `early_runtime._components` |
| A2 ✔ | **Confidence həmişə həddən aşağıdır.** Confidence = mövcud komponent / 7 = 4/7 = 0.57, minimum isə 0.60-dır. `EARLY_CONFIDENCE_BELOW_MINIMUM` hər qiymətləndirmədə çıxır, entry qapısı heç vaxt açılmır. | `early_scoring.py:541-547`, `early_decision.py:128` |
| A3 ✔ | **Token-2022 tokenləri alert ala bilmir.** Metadata oxunuşlarının 95%-i (377/397) `spl-token-2022`-dir (Pump.fun `create_v2`). Token security bunlara həmişə `TOKEN_2022_PROGRAM` xəbərdarlığı verir, nəticə CAUTION olur. Alert qapısı isə yalnız PASS qəbul edir. | `token_security.py:347-352`, `read_queries.py:1316`, `early_runtime.py:728` |
| A4 ✔ | **`STRONG_SETUP` (75), `HIGH_CONFLUENCE` (85) və `ENTRY_READY` (85) riyazi olaraq əlçatmazdır** (A1-in nəticəsi). Səhifədəki "High Confluence" və "Entry Ready" filtrləri heç vaxt nəticə verməyəcək. | `early_decision.py:123-127` |
| A5 ✔ | **Sellability əksər tokenlərdə UNKNOWN qalır.** Jupiter-in açarsız tier-i 1.1 s pacing ilə belə sorğuların ~1/3-nə 429 qaytardı (bu, paylaşılan IP-də ölçülüb, öz IP-də fərqli ola bilər). | 9.5 dəqiqəlik işləmə: 23/71 |

**Nəticə:** A1–A3 həll olunmadan səhifədə `ALERT READY` heç vaxt görünməyəcək.
Bu, kalibrasiya məsələsi deyil, skor modelinin canlı məlumatla uyğunsuzluğudur.

## 3. Səhifənin göstərdiyi məlumatda xətalar (P1)

| # | Tapıntı | Təsir |
| --- | --- | --- |
| B1 ✔ | **`ALERT READY` yalnız 5 dəqiqə yaşayır.** Qapı son 5 dəqiqədəki state-keçid event-inə bağlıdır (`ingested_at >= now − 5 min`). Siqnal tarixçəsi səhifədə yoxdur. | Həmin 5 dəqiqədə səhifəyə baxmırsansa, siqnalı görmürsən; sonradan "nə vaxt siqnal verdi" sualına cavab yoxdur. |
| B2 ✔ | **Telegram sütunu həmişə "NOT CONFIRMED".** Çatdırılmış alertlər yalnız `qualified_only` sorğusunda yüklənir, səhifə isə sətirləri ümumi siyahıdan çəkir. | Alert gəlsə belə, cədvəl onu göstərməyəcək. |
| B3 ✔ | **Sətir qərar anının snapshot-ıdır, canlı vəziyyət deyil.** "Age at decision" və likvidlik qərar anına aiddir. Cari qiymət, cari market cap və siqnaldan bəri dəyişiklik göstərilmir (`current_market_cap`, `multiple_since_discovery` demək olar həmişə null). | Siqnalın hələ keçərli olduğunu, yoxsa qiymətin artıq 3x getdiyini görə bilmirsən. |
| B4 ✔ | **5 dəqiqədən köhnə snapshot-da risk "UNKNOWN" olur.** Bu, heç qiymətləndirilməmiş tokenlə eyni görünür. | "Yoxlanıb, köhnəlib" ilə "heç yoxlanmayıb" ayırd edilmir. |
| B5 ✔ | **Namizədin "ilk hadisəsi" 14/71 halda launch deyil**, trade və ya buy event-idir (`instruction_type`: `trade_event` 9, `buy_v2` 4, `buy_exact_quote_in_v2` 1); 47-də isə ümumiyyətlə boşdur. | Signature, slot, creator və ad sahələri səhv event-dən götürülür və ya boş qalır. |
| B6 ✔ | **Qarışıq populyasiya.** Eyni cədvəldə Pump.fun launch-ları ilə yanaşı başqa kəşf yolundan gələn Meteora/Raydium/Orca tokenləri var; onların trade tape-i yoxdur. Venue iki cür yazılır: `PUMPFUN` və `PUMP.FUN`. | Venue filtri və müqayisə etibarsızdır. |
| B7 ✔ | **"Protocol source" sahəsində tranzaksiya signature-u görünür** (`first_seen_source = candidate.discovery_source`). | Mənbə adı əvəzinə 88 simvolluq sətir. |
| B8 ✔ | **Token-2022 extension-ları oxunmur** (`TOKEN_2022_EXTENSIONS_NOT_REPORTED`), halbuki RPC `jsonParsed` cavabında onlar var. | Transfer fee / hook kimi real riskli extension-lar ayırd edilmir; bütün Token-2022 tokenləri eyni xəbərdarlığı alır (A3-ü dərinləşdirir). |

## 4. Qərar üçün çatışmayan funksiyalar (P1–P2)

- **Giriş planı yoxdur.** Səhifə nə vaxt, hansı ölçüdə və hansı impact ilə
  girməyi göstərmir. Quote-lar yalnız 0.01 SOL probe və $1000 dərinlik
  sübutudur; sənin ölçün üçün impact hesablanmır.
- **Çıxış planı yoxdur.** Stop, take-profit və ləğv şərtləri (likvidlik
  düşməsi, creator satışı) yalnız paper pozisiyalar üçün exit engine-də var;
  manual alış üçün heç nə təklif olunmur və izlənmir.
- **Siqnalın keçmiş nəticəsi göstərilmir.** Əvvəlki `ALERT READY`
  siqnallarının neçəsi 2x/5x etdi, neçəsi rug oldu — bu statistika olmadan
  siqnalın dəyərini bilmək mümkün deyil.
- **Yeniləmə 30 saniyəlik polling-dir.** Pump.fun-da 30 saniyə qərar üçün
  uzun müddətdir; push (SSE/WebSocket) yoxdur.
- **Yalnız ilk səhifə (50–100 sətir) yüklənir**, sıralama və filtrlər yalnız
  həmin səhifənin daxilində işləyir.

## 5. Tövsiyə olunan ardıcıllıq

1. **Skor modelini canlı məlumata uyğunlaşdır (A1, A2).** Mənbəyi olmayan
   komponentləri skordan çıxarıb çəkiləri yenidən normallaşdır, və ya
   confidence-i yalnız mənbəyi olan komponentlər üzərində hesabla. Bu, hədlərin
   yenidən kalibrasiyasını tələb edir — owner qərarıdır.
2. **Token-2022-ni extension-a görə qiymətləndir (A3, B8).** Extension-ları
   RPC-dən oxu; təhlükəli extension yoxdursa PASS, varsa BLOCK/WARN.
3. **Siqnal tarixçəsi və Telegram statusu (B1, B2).** Alert-ə hazır olmuş
   hər namizədi vaxtı ilə saxla və göstər.
4. **Canlı vəziyyət (B3).** Sətirdə cari qiymət və siqnaldan bəri dəyişiklik.
5. **Namizəd identikliyi (B5–B7).** İlk hadisə həmişə create olsun; venue
   normallaşdırılsın; mənbə adı düzgün göstərilsin.
6. **Giriş/çıxış paneli və keçmiş nəticə statistikası (§4).**

# Becerilere katkıda bulunma

[English](../../../CONTRIBUTING.md) | [Русский](../ru/CONTRIBUTING.md) | [Español](../es/CONTRIBUTING.md) | [Français](../fr/CONTRIBUTING.md) | [Deutsch](../de/CONTRIBUTING.md) | [Português (Brasil)](../pt-BR/CONTRIBUTING.md) | [日本語](../ja/CONTRIBUTING.md) | [Italiano](../it/CONTRIBUTING.md) | [한국어](../ko/CONTRIBUTING.md) | [简体中文](../zh-CN/CONTRIBUTING.md) | Türkçe

Bu belge bir çeviridir; esas alınan kaynak [İngilizce sürümdür](../../../CONTRIBUTING.md).

Bu depo, yeniden kullanılabilir kolabse becerilerinin esas kaynağıdır. Her beceriyi
odaklı, taşınabilir, kaynağı belirtilebilir ve bağımsız kurulabilir tutun.

## Bir beceri eklemeden önce

1. Esas kaynağı belirleyin. Bu deponun becerinin sahibi mi olacağına yoksa başka
   bir kaynağı mı yansıtacağına karar verin.
2. Kopyalanan her talimatı, betiği, başvuru belgesini ve varlığı yeniden dağıtma
   hakkını doğrulayın. Aksi açıkça belirtilmedikçe özgün katkılar deponun
   Apache-2.0 lisansı kapsamında kabul edilir. Üçüncü taraf lisans dosyalarını,
   telif hakkı bildirimlerini, kaynak atıflarını ve değişiklik bildirimlerini
   koruyun; SPDX ifadelerini kataloğa kaydedin. Lisansı çözümlenmemiş üçüncü
   taraf materyallerini yayımlamayın.
3. Mevcut açıklamalarda örtüşen tetikleyicileri arayın. İş akışı aynı amaca
   hizmet ediyorsa mevcut beceriyi genişletin; bağımsız olarak yararlı bir
   tetikleyicisi ve tamamlanma ölçütü varsa yeni beceri ekleyin.
4. Küçük harfli, fiille başlayan, kısa çizgilerle ayrılmış, en fazla 63
   karakterlik bir ad seçin.

Tamamlanma ölçütü: dosyalar kopyalanmadan önce sahiplik, köken, lisans, kapsam
ve beceri adı bilinmelidir.

## Bir adayı uygulama boyunca izleme

Yeni veya genişletilmiş bir beceri bir GitHub Issue kaydından doğduğunda,
uygulama birincil dalda yer alana kadar bu Issue kaydını esas iş öğesi olarak
tutun.

1. Kaynak Issue kaydını uygulamanın pull request kaydında belirtin.
2. Pull request gövdesine `Closes #<issue-number>` ekleyin. Değişikliğin Issue
   kaydını kapatmaması gerekiyorsa nedenini ve amaçlanan son durumu açıkça belirtin.
3. Birleştirmeden sonra kapatma anahtar sözcüğünün uygulandığını varsaymak yerine
   Issue kaydını inceleyin. Beklenmedik şekilde açık kalmışsa uygulamanın pull
   request kaydına ve varsa sürüme bağlantılar vererek tamamlandı olarak kapatın.
4. Uygulama reddedildiyse, yerine başka bir çözüm geldiyse veya yalnızca kısmen
   teslim edildiyse açıklayıcı bir yorum bırakın ve uygun Issue durumunu kullanın;
   yalnızca bir dal veya pull request var olduğu için bir adayı tamamlanmış
   olarak bildirmeyin.

Tamamlanma ölçütü: uygulanan her aday kaynak Issue kaydından birleştirilmiş pull
request kaydına kadar izlenebilmeli ve Issue kaydının, uygulama veya tamamlanmama
açıklamasıyla doğrulanmış bir son durumu olmalıdır.

## Beceriyi ekleme veya taşıma

1. Yerel çalışmayı üzerine yazmadan kaynak ve hedef depoları eşitleyin.
2. `skills/<skill-name>/SKILL.md` oluşturun. YAML ön bilgisinde yalnızca `name`
   ve `description` tutun ve klasör adını `name` ile eşleştirin.
3. Deterministik yardımcıları `scripts/`, ajana yönelik ayrıntıları `references/`,
   çıktı materyallerini `assets/` ve isteğe bağlı arayüz meta verilerini
   `agents/openai.yaml` içine yerleştirin. Proje yapılandırmasını beceri klasörü
   dışında tutun.
4. Denetlenebilir tamamlanma ölçütleri içeren emir kipinde adımlar yazın.
   Gövdeyi 500 satırın altında tutun; dallara özgü ayrıntıları doğrudan başvuru
   bağlantılarıyla sunun.
5. `skill-catalog.json` dosyasına bir kayıt ekleyin:
   - `name` ve depoya göreli `path`;
   - belgelenmiş öncelik sırasını izleyen tam olarak bir birincil `category`;
   - yaşam döngüsü aşaması, kapsam, davranış ve entegrasyonlar için bir veya
     daha fazla kontrollü `tags`;
   - `status`: `experimental`, `stable` veya `deprecated`;
   - `maintainers` içinde GitHub kullanıcı adları;
   - desteklenen `platforms`;
   - `license` içinde SPDX ifadesi;
   - köken türü, kaynak, önceki adlar ve esas depo.
   Kategori ve etiket değerlerini `schemas/skill-catalog.schema.json` ile
   doğrulayın; olgunluk durumu her ikisinden de bağımsızdır.
6. Beceriyi amacı, kurulum notları ve gerekli ilk çalıştırma eylemiyle README
   kataloğuna ekleyin.
7. Deterministik betikler için testler ve beceriyi tetiklemesi ve tetiklememesi
   gereken gerçekçi istemler ekleyin. En az üç olumlu ve üç yakın olumsuz örneği
   `evals/<skill-name>.json` içinde saklayın ve bu dosyaya `skill-catalog.json`
   içinden `trigger_evals` olarak başvurun.

Taşınan bir beceri için bu depo esas kaynak haline geldikten sonra bile
geçmişini katalogda koruyun. Harici kaynaktan kopyalanarak tutulan bir beceri
için değişmez kaynak revizyonunu kaydedin, lisansını ve bildirimlerini beceri
klasöründe tutun ve üst kaynaktaki değişiklikleri yerel yamalardan ayrı tutun.
Üçüncü taraf içeriğini Apache-2.0 içeriğiyle birleştirmeden önce lisans
uyumluluğunu doğrulayın.

Tamamlanma ölçütü: okuyucu becerinin nereden geldiğini, sahibini, lisansını,
nerede çalıştığını ve nasıl doğrulanacağını belirleyebilmelidir.

## Yapılandırma sözleşmesi

Yapılandırılabilir her beceri, `skill-catalog.json` içinde bir `configuration`
nesnesi bildirir ve şu kurallara uyar:

- `configure` bir argv dizisidir, güvenle tekrarlanabilir, ilgisiz proje
  içeriğini korur ve aynı ikinci geçişte değişiklik olmadığını bildirir;
- `status` salt okunurdur, makine tarafından okunabilir JSON destekler, yalnızca
  bildirilen yapılandırma mevcut ve geçerliyse sıfır koduyla çıkar ve sırları
  asla yazdırmaz;
- proje ve kullanıcı kapsamları açıktır; yapılandırma kurulu beceri dizininin
  dışında kalır;
- JSON ve YAML yapılandırmaları pozitif tam sayı sürümüne, çözümlenmiş belgelerini
  tanımlayan paketlenmiş bir JSON Schema'ya ve hata halinde işlemi durduran bir
  geçiş komutuna sahiptir;
- yönetilen metin eşlenmiş, beceriye özgü işaretçiler kullanır, bozuk veya yinelenen
  işaretçileri reddeder ve kendi bloğu dışındaki metni yeniden yazmaz.
- durum tutmayan beceriler `none` biçimini kullanır, yalnızca salt okunur durum
  komutu sunar ve yer tutucu yapılandırma dosyaları uydurmamalıdır.

Komutlar kabuk dizeleri yerine diziler olarak saklanır. Çağıranın sağladığı
değerler için `<project-root>` gibi yer tutucular kullanın ve katalog komutuna
asla kimlik bilgisi koymayın. Geçiş adımlarını artımlı ve idempotent tutun;
nasıl geri düşürüleceğini tahmin etmek yerine daha yeni, bilinmeyen bir sürümü
reddedin.

Tamamlanma ölçütü: yapılandırmanın bulunduğu yerde tekrarlanan configure bayt
düzeyinde aynı çıktıyı üretmeli, status yazma işlemi yapmamalı, geçişler
desteklenen girdiyi korumalı ve testler eksik, bozuk, güncel ve eski
yapılandırmaları kapsamalıdır.

## Kullanıcıların güncelleme yolunu koruma

- Bir sürümde `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`,
  `skill-catalog.json.collection_version` ve tüm
  `skills/*/collection-metadata.json` sürümlerini aynı tutun.
- Hem `codex` hem `claude-code` için sabitlenmiş `skills` CLI üzerinden kopyalı
  kurulumu ve desteklenen en eski önceki sürümden güncellemeyi test edin.
- Proje/kullanıcı yapılandırmasını kurulu beceri klasörleri dışında tutun.
  Güncelleyicinin kullanılmayan bir beceri için sessizce yapılandırma
  oluşturmasına asla izin vermeyin.
- Gerekli geçişleri ve geri alma sınırlamalarını README'de ve değişiklik
  günlüğünde belgeleyin. Test edilmedikçe yapılandırmanın eski sürüme
  düşürülmesini desteklenmiyor olarak değerlendirin.
- Kişisel marketi değiştirirken ilgisiz kayıtları koruyun. Kurulu eklenti
  kopyasına bir önbellek yenileme son eki uygulayın ve etkinleştirmeden sonra
  yeni bir Codex görevi gerektirin.

Tamamlanma ölçütü: kullanıcı, depoya özel bilgiye ihtiyaç duymadan kurulu
sürümleri belirleyebilmeli, güncelleyebilmeli, mevcut yapılandırmayı
taşıyabilmeli, karışık sürümleri tanılayabilmeli ve önceki bir etiketi yeniden
kurabilmelidir.

## Ajanlar arası davranışı koruma

Paylaşılan `SKILL.md` talimatlarını ve yardımcıları taşınabilir tutun. Mevcut
komut satırı arayüzlerinde Codex varsayılan olarak kalır; açık bir Claude Code
hedefi `.claude/skills`, `CLAUDE.md` ve `/skill-name` kullanır. Mevcut `.agents`
yapılandırma API'lerini yalnızca başka bir tüketici için yeniden adlandırmak
amacıyla değiştirmeyin.

`agents/openai.yaml` dosyasını OpenAI arayüz meta verileri ve `.codex-plugin`
dizinini Codex paketlemesi olarak değerlendirin. Claude paketlemesi
`.claude-plugin` altında yer alır; hiçbir manifest diğerinin doğrulamasının
yerine sessizce geçemez. Bir ajan Codex Desktop görev listeleme gibi bir
yetenekten yoksunsa taşınabilir alt kümeyi koruyarak bu sınırlı işlemi
desteklenmiyor olarak bildirin.

Tamamlanma ölçütü: her iki tüketicinin kurulumu da aynı beceri içeriklerini
içermeli, kendi proje kuralı ve beceri düzenlerine uyulmalı, Codex varsayılanları
değişmemeli ve tüketici smoke testi kanıtları her iki ajanı da açıkça adlandırmalıdır.

## Becerileri yeteneklerine göre birleştirme

Küçük yetenek adlarını `provides`, zorunlu ön koşulları `requires` ve
engelleyici olmayan entegrasyonları `optional_integrations` içinde bildirin.
Adlandırılmış koleksiyon bileşimini yalnızca en az iki becerili, tekrarlanan
bir iş akışı için ekleyin. `required_steps` sıralıdır; `optional_steps` yalnızca
proje veya kullanıcı ilgili yeteneği etkinleştirdiğinde çalışır.

Bir becerinin iş akışını diğerine kopyalamayın. Ön koşul becerisini çağırın,
gözlemlenebilir tamamlanma sonucunu kullanın ve gerekli bir yetenek yoksa durun.
İsteğe bağlı bildirim veya günlük kaydı, başarılı bir birincil işlemi asla
gerçeğe aykırı bir başarıya dönüştürmemeli ve işlemin başarısızlığını gizlememelidir.

Tamamlanma ölçütü: gerekli her yeteneğin sağlayıcısı olmalı, bileşim adımları
mevcut becerilere birer kez başvurmalı ve sıra için bir entegrasyon testi veya
yürütülebilir tamamlanma ölçütü bulunmalıdır.

## Yaşam döngüsü durumunu yönetme

- Yeni veya önemli ölçüde yeniden tasarlanmış bir beceriyi meta verileri,
  deterministik yardımcıları, platformlar arası testleri, geliştirme tetikleyici
  derlemi, bağımsız ileri testi, kopyalı kurulum smoke testi ve sürüm holdout
  testi geçene kadar `experimental` olarak tutun. Yalnızca metinden oluşan
  bir iş akışı için paketlenmiş betikler gibi uygulanmayan gereklilikler,
  uygulanamaz olarak kaydedilebilir.
- Bir beceriyi yalnızca sürümlenmiş bir koleksiyon yayımında `stable` olarak
  işaretleyin. Bu sürüm numarasıyla `stable_since` ekleyin. Kararlı durum,
  belgelenmiş girdilerin, yapılandırma konumlarının, güvenlik sınırlarının ve
  CLI davranışının mevcut koleksiyon ana sürümü içinde uyumlu kalacağı veya
  geçiş rehberliği sağlanacağı anlamına gelir.
- Kaldırmadan önce beceriyi `deprecated` olarak işaretleyin. Desteklenen
  alternatifini veya geçiş yolunu beceride ve değişiklik günlüğünde belirtin;
  acil bir güvenlik sorunu daha erken kaldırmayı gerektirmedikçe en az bir
  ikincil sürüm boyunca koruyun.

Tamamlanma ölçütü: yaşam döngüsü durumu gözlemlenebilir doğrulamaya dayanmalı ve
açık bir uyumluluk beklentisi aktarmalıdır.

## Kurulu içeriğin kökenini koruma

Bilinen bir beceri adını yalnızca aday olarak değerlendirin, asla koleksiyon
kimliği olarak değil. Harici kilit kaynağını kurulu `collection-metadata.json`
ile ilişkilendirin. Desteklenen GitHub yazımlarını
`https://github.com/kolabse/skills` biçimine normalleştirin; yerel geliştirme
kaynaklarını çalışma kopyasının dizin adına bağımlı olmadan eklenti manifesti,
katalog ve istenen beceri içeriğinden doğrulayın.

Aynı adlı başka kaynaklı beceride veya çelişkili meta verilerde işlemi güvenli
biçimde durdurun. Eski kurulumun benimsenmesini açık bir tercih olarak tutun ve
yalnızca kilit kaynağının kendisi doğrulandığında izin verin; başarılı benimseme,
güncel meta veriler ve sağlıklı bir güncelleme sonrası tanıyla sonuçlanmalıdır.

Tamamlanma ölçütü: durum çıktısı köken sınıflandırmasını sunmalı, güncelleme
yalnızca doğrulanmış becerileri (veya açıkça benimsenmiş eski becerileri) seçmeli
ve testler kaynak çakışmalarını, sürüm referanslarını, yeniden adlandırılmış
yerel çalışma kopyalarını ve eski kurulumları kapsamalıdır.

## Kullanıcı otomasyonunu incelenebilir tutma

`plan` salt okunur kalmalıdır: kurucuları, geçişleri veya ağ işlemlerini
çağırmamalıdır. Plan ve sonuç verileri için sürümlenmiş JSON Schema'lar
yayımlayın; insanlara yönelik CLI çıktısını ayrıştırmadan değişmedi,
güncellendi, taşındı, atlandı, engellendi ve başarısız durumlarını ayırt edin.

Genel keşfi belgelenmiş kilit ve kurulum kökleriyle sınırlayın. Olası kurulumları
bulmak için ana dizini taramayın. Aynı köken, açık seçim ve güncelleme sonrası
tanı kurallarını genel kapsamda da uygulayın.

Bağımsız başlangıç yardımcısı, çıkarmadan önce arşiv sağlama toplamını,
çalıştırmadan önce GitHub derleme kökenini doğrulamalı; dizin dışına çıkış
ve sembolik bağlantı arşiv girdilerini reddetmeli, geçici dizin kullanmalı ve
yöneticinin çıkış kodunu iletmelidir. Tasdiksiz çevrimdışı çalıştırmayı açık
bir kısıtlı güvence modu bayrağının arkasında tutun.

Tamamlanma ölçütü: şemalar ayrıştırılmalı, deneme çalıştırması test verilerini
bayt düzeyinde aynı bırakmalı, genel kapsam test verileri desteklenen ve
belirsiz düzenleri kapsamalı ve başlangıç smoke testi desteklenen her CI
işletim sisteminde geçmelidir.

## Değişikliği doğrulama

Çalıştırın:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py --agent codex
python scripts/smoke_install.py --agent claude-code
```

Tetikleyici derlemini, becerinin ilk çalıştırma yolu dahil gerçek bir ajanla
sınayın. Yapısal CI kontrolleri derlemin bütünlüğünü korur ancak modelin
çağrılmasının gözlemlenmesinin yerini tutmaz. İstemleri ve gözlemlenen sonucu
pull request kaydına ekleyin.

Koleksiyon genelinde tetikleyici değerlendirmesi için kör bir test paketi
hazırlayın ve seçicinin gözlemlerini puanlayın:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Seçiciler birden fazla beceri seçebilir veya hiçbirini seçmeyebilir. Kaynak
değerlendirme dosyalarını, beklenen etiketleri, yazar gerekçelerini, şüphelenilen
başarısızlıkları veya önceki raporları seçiciye göstermeyin. Tahmin meta
verilerine sağlayıcı/model kimliğini kaydedin, ham tahminleri inceleme
kanıtlarıyla saklayın ve açıklamayı değiştirmeden önce her yanlış olumlu ve
yanlış olumsuz sonucu inceleyin. Yakın iş akışlarını belirsizleştirecekse daha
yüksek bir puan tetikleyiciyi genişletmek için yeterli gerekçe değildir.

`evals/release-holdout-vN.json` dosyasını yalnızca ekleme yapılabilen sürüm kanıtı
olarak değerlendirin. Açıklamaları ayarlarken etkin holdout'u okumayın veya
çalıştırmayın. Mevcut holdout sürümleri değişmezdir: `vN+1` oluşturun, katalog
adını, yolunu ve esas özet değerini güncelleyin ve yayımlanmış tüm sürümleri
koruyun. Etkin holdout'u yalnızca aday açıklamalar dondurulduktan sonra
çalıştırın; ardından raporunu aynı holdout sürümü ve seçici yapılandırmasıyla
üretilen bir temel raporla karşılaştırın. İddia özet değerleri farklı raporları
asla karşılaştırmayın. Yayımdan sonra kabul edilen raporu `evals/baselines/`
altında saklayın ve kataloğun temel rapor işaretçisini güncelleyin; temel rapor
dosyaları sürüm kanıtıdır ve yeniden yazılmamalıdır. Seçici deterministik
değilse en az üç olmak üzere tek sayıda bağımsız kör çalışma kullanın ve
çoğunluk oyu birleştirmesini karşılaştırın. Tek bir gözlemi geçene kadar yeniden
çalıştırmayın veya geçerli başarısız gözlemleri atmayın.

Tamamlanma ölçütü: her komut desteklenen her işletim sisteminde geçmeli ve pull
request kontrol listesi etkilenen beceriye ilişkin kanıtları içermelidir.

## Sürüm yayımlama zincirini koruma

- Her harici GitHub Action'ı tam commit SHA'sına sabitleyin ve sürümünü bir
  yorumda koruyun. İncelenecek SHA güncellemelerini Dependabot önersin.
- Her iş akışına yalnızca ihtiyaç duyduğu `GITHUB_TOKEN` izinlerini verin.
- Sürüm arşivlerini `scripts/build_release.py` ile oluşturun; varlıkları
  yüklemeden önce `SHA256SUMS` doğrulayın.
- Her sürüm varlığı için GitHub çıktı tasdikleri yayımlayın ve bunları
  `gh attestation verify <artifact> --repo kolabse/skills` ile doğrulayın.
- Mevcut bir sürüm varlığını asla değiştirmeyin. Tekrarlanan iş akışı çalışması,
  yayımlanan baytların aynı olduğunu doğrulamalı veya başarısız olmalıdır.
- Sürüm etiketlerini değişmez tutun. Mevcut etiketi taşımak veya kaynak commit'ini
  değiştirmek yerine düzeltmeyi yeni bir sürüm olarak yayımlayın.

Tamamlanma ölçütü: etiket incelenmiş commit'e çözülmeli, yüklenen varlıklar
`SHA256SUMS` ile eşleşmeli ve iş akışı bağımlılıkları değişmez referanslar olmalıdır.

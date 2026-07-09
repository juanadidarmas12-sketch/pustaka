// Manually curated raw connection edges per author, derived from influencedBy/influenced
// in books/authors.json (see DESIGN_CONNECTIONS.md §2.5). Each entry: [to, type, note?].
// `type` default when omitted downstream = 'pengaruh'. `to` uses exact catalog spelling
// when the target is one of the 77 authors; otherwise free-text (person, movement, or event).
// This is a scratch/build-time data file consumed by build_connections.js — not shipped to the app.

module.exports = {
  "Niccolò Machiavelli": [
    ["Livy", "pengaruh", "sejarawan Romawi favoritnya"],
    ["Cicero", "pengaruh"],
    ["Xenophon", "pengaruh"],
    ["Thomas Hobbes", "pengaruh"],
    ["Realisme politik & Hubungan Internasional modern", "pengaruh"]
  ],
  "Marcus Aurelius": [
    ["Epictetus", "guru", "fondasi Stoisisme batinnya"],
    ["Junius Rusticus", "guru", "mengenalkan catatan Epictetus"],
    ["Zeno dari Citium", "pengaruh", "pendiri Stoisisme"],
    ["Seneca", "pengaruh", "sesama penulis Stoa"],
    ["Matthew Arnold", "pengaruh", "penyair Victorian yang mengaguminya"],
    ["Gerakan Stoisisme modern", "pengaruh"]
  ],
  "Sun Tzu": [
    ["Filsafat Taois awal", "pengaruh", "kelenturan mengalahkan kekakuan"],
    ["Mao Zedong", "pengaruh", "strategi perang gerilya"]
  ],
  "Karl Marx & Friedrich Engels": [
    ["G.W.F. Hegel", "pengaruh"],
    ["Ludwig Feuerbach", "pengaruh"],
    ["Adam Smith", "pengaruh", "ekonom klasik Inggris"],
    ["David Ricardo", "pengaruh", "ekonom klasik Inggris"],
    ["Revolusi-revolusi Eropa 1848", "pengaruh"],
    ["Vladimir Lenin", "pengaruh", "Revolusi Rusia"],
    ["Revolusi Tiongkok", "pengaruh"],
    ["Gerakan buruh dan sosialis dunia", "pengaruh"],
    ["Sosiologi dan ilmu sosial modern", "pengaruh"],
    ["Karl Marx", "kolaborator", "penulis solo di katalog ini"]
  ],
  "Plato": [
    ["Socrates", "guru"],
    ["Pythagoras", "pengaruh"],
    ["Parmenides", "pengaruh"],
    ["Heraclitus", "pengaruh"],
    ["Aristotle", "murid"],
    ["Neoplatonisme", "pengaruh"],
    ["Agustinus dari Hippo", "pengaruh", "filsafat Kristen abad pertengahan"],
    ["Tradisi filsafat Barat", "pengaruh"]
  ],
  "Edward Gibbon": [
    ["Tacitus", "pengaruh", "sejarawan klasik"],
    ["Livy", "pengaruh", "sejarawan klasik"],
    ["Montesquieu", "pengaruh"],
    ["Winston Churchill", "pengaruh", "mengagumi gaya prosanya"],
    ["Penulisan sejarah naratif modern", "pengaruh"],
    ["Diskursus kejatuhan imperium modern", "pengaruh"]
  ],
  "David Ricardo": [
    ["Adam Smith", "pengaruh"],
    ["Thomas Robert Malthus", "pengaruh"],
    ["Karl Marx", "pengaruh", "memakai teori nilai kerja, beda simpulan"],
    ["John Stuart Mill", "pengaruh"],
    ["Teori perdagangan internasional modern", "pengaruh"],
    ["Ekonomi klasik dan neoklasik", "pengaruh"]
  ],
  "Alexis de Tocqueville": [
    ["Montesquieu", "pengaruh"],
    ["Ilmu politik dan sosiologi modern", "pengaruh"],
    ["Diskursus populisme dan polarisasi kontemporer", "pengaruh"],
    ["Pemikir komunitarian abad ke-20", "pengaruh"]
  ],
  "John Stuart Mill": [
    ["James Mill", "guru", "ayahnya"],
    ["Jeremy Bentham", "pengaruh"],
    ["Harriet Taylor Mill", "kolaborator", "istrinya, mitra intelektual"],
    ["William Wordsworth", "pengaruh", "puisi Romantik"],
    ["Samuel Taylor Coleridge", "pengaruh", "puisi Romantik"],
    ["Liberalisme politik modern", "pengaruh"],
    ["Gerakan hak pilih perempuan", "pengaruh"],
    ["Filsafat utilitarian lanjutan", "pengaruh"]
  ],
  "Friedrich Nietzsche": [
    ["Arthur Schopenhauer", "pengaruh"],
    ["Richard Wagner", "menentang", "awalnya kagum, lalu berbalik menentang"],
    ["Filologi dan tragedi Yunani klasik", "pengaruh"],
    ["Eksistensialisme", "pengaruh", "Sartre, Camus"],
    ["Postmodernisme", "pengaruh", "Foucault, Derrida"],
    ["Sigmund Freud", "pengaruh"],
    ["Sastra modern abad ke-20", "pengaruh"]
  ],
  "Herodotus": [
    ["Homer", "pengaruh", "tradisi epik lisan Yunani"],
    ["Perang Yunani-Persia", "pengaruh"],
    ["Thucydides", "menentang", "bereaksi dengan metode lebih ketat"],
    ["Tradisi penulisan sejarah naratif Barat", "pengaruh"],
    ["Antropologi dan etnografi modern", "pengaruh"]
  ],
  "Thorstein Veblen": [
    ["Karl Marx", "pengaruh", "kritik kapitalisme, beda pendekatan"],
    ["Charles Darwin", "pengaruh", "evolusi diterapkan pada institusi sosial"],
    ["Sosiologi ekonomi modern", "pengaruh"],
    ["Studi konsumerisme dan status sosial", "pengaruh"],
    ["Ekonomi kelembagaan (institutional economics)", "pengaruh"]
  ],
  "W. E. B. Du Bois": [
    ["William James", "guru", "gurunya di Harvard"],
    ["Pan-Afrikanisme", "pengaruh", "tradisi intelektual & gerakan kemerdekaan Afrika"],
    ["Gerakan hak sipil Amerika", "pengaruh"],
    ["Studi ras dan sosiologi kritis modern", "pengaruh"]
  ],
  "John Locke": [
    ["Robert Boyle", "pengaruh", "lingkungan ilmiah Royal Society"],
    ["Earl of Shaftesbury", "pengaruh", "patronnya"],
    ["Perang Saudara Inggris", "pengaruh"],
    ["Thomas Jefferson", "pengaruh", "Deklarasi Kemerdekaan Amerika"],
    ["Revolusi Amerika", "pengaruh"],
    ["Liberalisme klasik modern", "pengaruh"],
    ["Voltaire", "pengaruh", "Pencerahan Prancis"]
  ],
  "Thomas More": [
    ["Erasmus dari Rotterdam", "pengaruh", "sahabat dekatnya"],
    ["Plato", "pengaruh", "terutama 'The Republic'"],
    ["Humanisme Renaisans", "pengaruh"],
    ["Tradisi sastra utopia dan distopia modern", "pengaruh"],
    ["Sosialisme utopis abad ke-19", "pengaruh"],
    ["Reformasi sosial dan keadilan ekonomi", "pengaruh"]
  ],
  "Henry David Thoreau": [
    ["Ralph Waldo Emerson", "guru", "mentor dan tetangganya"],
    ["Transendentalisme Amerika", "pengaruh"],
    ["Filsafat Hindu dan Timur", "pengaruh"],
    ["Mahatma Gandhi", "pengaruh"],
    ["Martin Luther King Jr.", "pengaruh"],
    ["Gerakan lingkungan dan konservasi alam modern", "pengaruh"],
    ["Gerakan hidup sederhana (simple living)", "pengaruh"]
  ],
  "Thomas Paine": [
    ["Benjamin Franklin", "pengaruh"],
    ["John Locke", "pengaruh", "Pencerahan"],
    ["Jean-Jacques Rousseau", "pengaruh", "Pencerahan"],
    ["Revolusi Amerika", "pengaruh"],
    ["Revolusi Prancis", "pengaruh"],
    ["Tradisi pamflet politik dan jurnalisme persuasif modern", "pengaruh"],
    ["Gerakan republikanisme demokratis", "pengaruh"]
  ],
  "Laozi": [
    ["Tradisi kearifan rakyat dan kosmologi Tiongkok kuno", "pengaruh"],
    ["Taoisme sebagai agama dan filsafat", "pengaruh"],
    ["Zhuangzi", "pengaruh"],
    ["Seni bela diri dan pengobatan tradisional Tiongkok", "pengaruh"],
    ["Gerakan mindfulness dan minimalisme modern", "pengaruh"]
  ],
  "Thucydides": [
    ["Herodotus", "menentang", "mengkritik metode pendahulunya"],
    ["Sofisme dan retorika Athena", "pengaruh"],
    ["Ilmu hubungan internasional dan teori realisme", "pengaruh"],
    ["Historiografi ilmiah modern", "pengaruh"],
    ["Perangkap Thukydides", "pengaruh", "analisis geopolitik kontemporer"]
  ],
  "Mary Wollstonecraft": [
    ["Jean-Jacques Rousseau", "menentang", "mengkritik keras soal pendidikan perempuan"],
    ["Revolusi Prancis", "pengaruh"],
    ["Joseph Johnson", "pengaruh", "lingkaran penerbit radikal London"],
    ["John Stuart Mill", "pengaruh", "'The Subjection of Women'"],
    ["Gerakan hak pilih perempuan (suffragette)", "pengaruh"],
    ["Feminisme gelombang pertama dan kedua", "pengaruh"]
  ],
  "Thomas Hobbes": [
    ["Euclid", "pengaruh"],
    ["Galileo Galilei", "pengaruh"],
    ["Perang Saudara Inggris", "pengaruh"],
    ["Niccolò Machiavelli", "pengaruh"],
    ["John Locke", "pengaruh"],
    ["Jean-Jacques Rousseau", "pengaruh"],
    ["Baruch Spinoza", "pengaruh"],
    ["Teori kontrak sosial modern", "pengaruh"]
  ],
  "Aristotle": [
    ["Plato", "pengaruh"],
    ["Socrates", "pengaruh"],
    ["Thomas Aquinas", "pengaruh"],
    ["Skolastik Abad Pertengahan", "pengaruh"],
    ["Ibnu Rusyd (Averroes)", "pengaruh"],
    ["Etika kebajikan modern", "pengaruh"]
  ],
  "Epictetus": [
    ["Musonius Rufus", "guru"],
    ["Zeno dari Citium", "pengaruh"],
    ["Stoisisme", "pengaruh"],
    ["Marcus Aurelius", "pengaruh"],
    ["Terapi Perilaku Kognitif (CBT) modern", "pengaruh"],
    ["Gerakan Stoisisme modern", "pengaruh"]
  ],
  "Lucretius": [
    ["Epicurus", "pengaruh"],
    ["Democritus", "pengaruh"],
    ["Pemikiran atomis Renaisans", "pengaruh"],
    ["Materialisme ilmiah modern", "pengaruh"],
    ["Virgil", "pengaruh"],
    ["Horace", "pengaruh"]
  ],
  "Boethius": [
    ["Plato", "pengaruh"],
    ["Neoplatonisme", "pengaruh"],
    ["Stoisisme", "pengaruh"],
    ["Geoffrey Chaucer", "pengaruh"],
    ["Dante Alighieri", "pengaruh"],
    ["Teologi Skolastik", "pengaruh"]
  ],
  "René Descartes": [
    ["Euclid", "pengaruh", "geometrinya"],
    ["Galileo Galilei", "pengaruh"],
    ["Pendidikan Skolastik Jesuit", "pengaruh"],
    ["Baruch Spinoza", "pengaruh"],
    ["Empirisisme Inggris", "menentang", "muncul sebagai tandingan pemikirannya"],
    ["Isaac Newton", "pengaruh"]
  ],
  "Baruch Spinoza": [
    ["René Descartes", "pengaruh"],
    ["Yudaisme", "pengaruh"],
    ["Stoisisme", "pengaruh"],
    ["Thomas Hobbes", "pengaruh"],
    ["Pencerahan Eropa", "pengaruh"],
    ["Albert Einstein", "pengaruh"],
    ["Kritik biblika modern", "pengaruh"],
    ["G.W.F. Hegel", "pengaruh"]
  ],
  "David Hume": [
    ["John Locke", "pengaruh"],
    ["George Berkeley", "pengaruh"],
    ["Francis Bacon", "pengaruh"],
    ["Immanuel Kant", "pengaruh"],
    ["Positivisme logis", "pengaruh"],
    ["Adam Smith", "sezaman", "sahabat dekat, Pencerahan Skotlandia"]
  ],
  "Immanuel Kant": [
    ["David Hume", "pengaruh"],
    ["Jean-Jacques Rousseau", "pengaruh"],
    ["Gottfried Leibniz", "pengaruh"],
    ["G.W.F. Hegel", "pengaruh"],
    ["Arthur Schopenhauer", "pengaruh"],
    ["Etika deontologis modern", "pengaruh"],
    ["Deklarasi hak asasi manusia", "pengaruh"]
  ],
  "Arthur Schopenhauer": [
    ["Immanuel Kant", "pengaruh"],
    ["Plato", "pengaruh"],
    ["Filsafat Hindu (Upanishad)", "pengaruh"],
    ["Buddhisme", "pengaruh"],
    ["Friedrich Nietzsche", "pengaruh"],
    ["Sigmund Freud", "pengaruh"],
    ["Richard Wagner", "pengaruh"]
  ],
  "Francis Bacon": [
    ["Aristotle", "menentang", "lawan tanding metode skolastiknya"],
    ["Niccolò Machiavelli", "pengaruh"],
    ["Humanisme Renaisans", "pengaruh"],
    ["Royal Society", "pengaruh"],
    ["Isaac Newton", "pengaruh"],
    ["Metode ilmiah modern", "pengaruh"],
    ["Empirisisme Inggris", "pengaruh"]
  ],
  "George Berkeley": [
    ["John Locke", "pengaruh"],
    ["René Descartes", "pengaruh"],
    ["Nicolas Malebranche", "pengaruh"],
    ["David Hume", "pengaruh"],
    ["Immanuel Kant", "pengaruh"],
    ["Idealisme modern", "pengaruh"]
  ],
  "William James": [
    ["Charles Sanders Peirce", "pengaruh"],
    ["Ralph Waldo Emerson", "pengaruh"],
    ["Charles Darwin", "pengaruh", "teori evolusi"],
    ["John Dewey", "pengaruh"],
    ["Pragmatisme Amerika", "pengaruh"],
    ["Psikologi fungsionalis", "pengaruh"]
  ],
  "Bertrand Russell": [
    ["Gottlob Frege", "pengaruh"],
    ["Alfred North Whitehead", "kolaborator", "co-author Principia Mathematica"],
    ["John Stuart Mill", "pengaruh"],
    ["Ludwig Wittgenstein", "murid", "muridnya di Cambridge"],
    ["Filsafat analitik modern", "pengaruh"],
    ["Gerakan anti-nuklir", "pengaruh"]
  ],
  "Ralph Waldo Emerson": [
    ["Immanuel Kant", "pengaruh", "via idealisme Jerman"],
    ["Samuel Taylor Coleridge", "pengaruh"],
    ["Thomas Carlyle", "pengaruh"],
    ["Filsafat Hindu", "pengaruh"],
    ["Henry David Thoreau", "pengaruh"],
    ["Walt Whitman", "pengaruh"],
    ["Friedrich Nietzsche", "pengaruh"],
    ["William James", "pengaruh"]
  ],
  "Confucius": [
    ["Dinasti Zhou awal", "pengaruh"],
    ["Duke of Zhou", "pengaruh"],
    ["Tradisi ritual Tiongkok kuno", "pengaruh"],
    ["Mencius", "pengaruh"],
    ["Konfusianisme", "pengaruh"],
    ["Sistem ujian birokrasi kekaisaran Tiongkok", "pengaruh"]
  ],
  "Blaise Pascal": [
    ["Jansenisme", "pengaruh"],
    ["René Descartes", "menentang", "sebagai lawan tanding"],
    ["Michel de Montaigne", "pengaruh"],
    ["Eksistensialisme Kristen", "pengaruh"],
    ["Teori probabilitas modern", "pengaruh"],
    ["Apologetika Kristen modern", "pengaruh"]
  ],
  "Alexander Hamilton, James Madison & John Jay": [
    ["Montesquieu", "pengaruh"],
    ["John Locke", "pengaruh"],
    ["Kegagalan Articles of Confederation", "pengaruh"],
    ["Konstitusionalisme Amerika modern", "pengaruh"],
    ["Mahkamah Agung Amerika Serikat", "pengaruh"],
    ["Teori checks and balances", "pengaruh"]
  ],
  "Jean-Jacques Rousseau": [
    ["John Locke", "pengaruh"],
    ["Thomas Hobbes", "menentang", "sebagai lawan tanding"],
    ["Madame de Warens", "pengaruh", "pelindung di masa muda"],
    ["Revolusi Prancis", "pengaruh"],
    ["Immanuel Kant", "pengaruh"],
    ["Romantisisme", "pengaruh"],
    ["Teori pendidikan modern", "pengaruh"]
  ],
  "Edmund Burke": [
    ["John Locke", "pengaruh"],
    ["David Hume", "pengaruh"],
    ["Montesquieu", "pengaruh"],
    ["Cicero", "pengaruh"],
    ["Konservatisme modern", "pengaruh"],
    ["Alexis de Tocqueville", "pengaruh"],
    ["Russell Kirk", "pengaruh"],
    ["Pemikiran politik Inggris abad ke-19", "pengaruh"]
  ],
  "Emma Goldman": [
    ["Mikhail Bakunin", "pengaruh"],
    ["Peter Kropotkin", "pengaruh"],
    ["Peristiwa Haymarket", "pengaruh"],
    ["Alexander Berkman", "kolaborator", "pasangan & rekan seperjuangan"],
    ["Gerakan hak reproduksi Amerika", "pengaruh"],
    ["Anarkisme feminis", "pengaruh"],
    ["Gerakan buruh Amerika awal abad ke-20", "pengaruh"]
  ],
  "Walter Bagehot": [
    ["Adam Smith", "pengaruh"],
    ["David Ricardo", "pengaruh"],
    ["Kebijakan bank sentral modern", "pengaruh"],
    ["John Maynard Keynes", "pengaruh"],
    ["Studi konstitusi perbandingan", "pengaruh"]
  ],
  "Mikhail Bakunin": [
    ["G.W.F. Hegel", "pengaruh"],
    ["Pierre-Joseph Proudhon", "pengaruh"],
    ["Pemberontakan Eropa 1848", "pengaruh"],
    ["Peter Kropotkin", "pengaruh"],
    ["Gerakan anarko-sindikalisme", "pengaruh"],
    ["Emma Goldman", "pengaruh"],
    ["Perang Saudara Spanyol (sayap anarkis)", "pengaruh"]
  ],
  "Peter Kropotkin": [
    ["Charles Darwin", "pengaruh"],
    ["Mikhail Bakunin", "pengaruh"],
    ["Gerakan anarko-komunisme", "pengaruh"],
    ["Ekologi sosial", "pengaruh"],
    ["Emma Goldman", "pengaruh"],
    ["Gerakan koperasi", "pengaruh"]
  ],
  "Plutarch": [
    ["Plato", "pengaruh"],
    ["Tradisi biografi Yunani", "pengaruh"],
    ["William Shakespeare", "pengaruh"],
    ["Ralph Waldo Emerson", "pengaruh"],
    ["Genre biografi Barat modern", "pengaruh"]
  ],
  "Julius Caesar": [
    ["Gaius Marius", "pengaruh"],
    ["Tradisi militer Romawi", "pengaruh"],
    ["Pompey", "menentang", "rivalitas berujung perang saudara"],
    ["Augustus", "pengaruh"],
    ["Kekaisaran Romawi", "pengaruh"],
    ["Konsep kepemimpinan otokratis Barat", "pengaruh"]
  ],
  "Tacitus": [
    ["Sallust", "pengaruh"],
    ["Tradisi historiografi Romawi", "pengaruh"],
    ["Edward Gibbon", "pengaruh"],
    ["Historiografi politik modern", "pengaruh"],
    ["Niccolò Machiavelli", "pengaruh"]
  ],
  "Xenophon": [
    ["Socrates", "guru"],
    ["Cyrus Muda", "pengaruh", "pengalaman militer di Persia"],
    ["Studi kepemimpinan militer klasik", "pengaruh"],
    ["Alexander Agung", "pengaruh", "via studi taktik"],
    ["Tradisi memoar perang", "pengaruh"]
  ],
  "Suetonius": [
    ["Tradisi biografi Romawi", "pengaruh"],
    ["Hadrian", "pengaruh", "akses arsip kekaisaran"],
    ["Plutarch", "pengaruh"],
    ["Einhard", "pengaruh"],
    ["Genre biografi kekaisaran", "pengaruh"],
    ["Persepsi populer sejarah Romawi", "pengaruh"]
  ],
  "Thomas Carlyle": [
    ["Johann Wolfgang von Goethe", "pengaruh"],
    ["Calvinisme Skotlandia", "pengaruh"],
    ["Filsafat idealisme Jerman", "pengaruh"],
    ["Charles Dickens", "pengaruh"],
    ["John Ruskin", "pengaruh"],
    ["Ralph Waldo Emerson", "pengaruh"]
  ],
  "H. G. Wells": [
    ["Thomas Henry Huxley", "guru", "gurunya di Normal School of Science"],
    ["Charles Darwin", "pengaruh"],
    ["Perang Dunia Pertama", "pengaruh", "traumanya"],
    ["Genre fiksi ilmiah modern", "pengaruh"],
    ["Gerakan pemerintahan dunia", "pengaruh"],
    ["George Orwell", "pengaruh"]
  ],
  "Benjamin Franklin": [
    ["Pencerahan Eropa", "pengaruh"],
    ["John Locke", "pengaruh"],
    ["Tradisi Puritan Boston", "pengaruh"],
    ["Samuel Smiles", "pengaruh"],
    ["Etos kerja Amerika", "pengaruh"],
    ["Konstitusi Amerika Serikat", "pengaruh"]
  ],
  "Frederick Douglass": [
    ["William Lloyd Garrison", "pengaruh"],
    ["Alkitab", "pengaruh"],
    ["Gerakan abolisionis", "pengaruh"],
    ["Booker T. Washington", "pengaruh"],
    ["W. E. B. Du Bois", "pengaruh"],
    ["Gerakan hak sipil Amerika", "pengaruh"]
  ],
  "Marco Polo": [
    ["Niccolò dan Maffeo Polo", "pengaruh", "ayah dan pamannya"],
    ["Tradisi dagang Venesia", "pengaruh"],
    ["Kubilai Khan", "pengaruh"],
    ["Christopher Columbus", "pengaruh"],
    ["Eksplorasi Eropa ke Asia", "pengaruh"],
    ["Sastra perjalanan Barat", "pengaruh"]
  ],
  "Polybius": [
    ["Aristotle", "pengaruh"],
    ["Keluarga Scipio", "pengaruh"],
    ["Tradisi historiografi pragmatis Yunani", "pengaruh"],
    ["Cicero", "pengaruh"],
    ["Niccolò Machiavelli", "pengaruh"],
    ["Perancang Konstitusi Amerika Serikat", "pengaruh"]
  ],
  "Einhard": [
    ["Suetonius", "pengaruh"],
    ["Charlemagne", "pengaruh"],
    ["Renaisans Karoling", "pengaruh"],
    ["Historiografi biografi abad pertengahan", "pengaruh"],
    ["Persepsi populer tentang Charlemagne", "pengaruh"]
  ],
  "Flavius Josephus": [
    ["Tradisi keimaman Yahudi", "pengaruh"],
    ["Vespasian", "pengaruh"],
    ["Filsafat Farisi dan Eseni", "pengaruh"],
    ["Historiografi Kristen awal", "pengaruh"],
    ["Studi sejarah Yudea kuno", "pengaruh"]
  ],
  "Karl Marx": [
    ["G.W.F. Hegel", "pengaruh"],
    ["Ludwig Feuerbach", "pengaruh"],
    ["Karl Marx & Friedrich Engels", "kolaborator", "kolaborasi dengan Engels"],
    ["Adam Smith", "menentang", "membangun teori nilai kerja darinya lalu mengkritiknya"],
    ["David Ricardo", "pengaruh"],
    ["Vladimir Lenin", "pengaruh"],
    ["Gerakan buruh internasional", "pengaruh"],
    ["Mikhail Bakunin", "menentang", "perseteruan di International"],
    ["Sosiologi dan ekonomi politik modern", "pengaruh"]
  ],
  "Thomas Robert Malthus": [
    ["Daniel Malthus", "pengaruh", "ayahnya"],
    ["William Godwin", "menentang", "via perdebatan"],
    ["Adam Smith", "pengaruh"],
    ["Charles Darwin", "pengaruh"],
    ["David Ricardo", "pengaruh"],
    ["Kebijakan populasi modern", "pengaruh"],
    ["Ekonomi lingkungan", "pengaruh"]
  ],
  "Henry George": [
    ["Adam Smith", "pengaruh"],
    ["Demam Emas California", "pengaruh"],
    ["John Stuart Mill", "pengaruh"],
    ["Georgisme", "pengaruh"],
    ["Gerakan pajak tunggal", "pengaruh"],
    ["Kebijakan pajak properti modern", "pengaruh"]
  ],
  "John Maynard Keynes": [
    ["Alfred Marshall", "guru", "gurunya di Cambridge"],
    ["Perundingan Versailles", "pengaruh"],
    ["Depresi Besar", "pengaruh"],
    ["Kebijakan New Deal", "pengaruh"],
    ["Ekonomi makro modern", "pengaruh"],
    ["Negara kesejahteraan pascaperang", "pengaruh"]
  ],
  "Adam Smith": [
    ["David Hume", "sezaman", "sahabat dekat, Pencerahan Skotlandia"],
    ["Para Fisiokrat Prancis", "pengaruh"],
    ["Francis Hutcheson", "guru", "gurunya di Glasgow"],
    ["David Ricardo", "pengaruh"],
    ["Karl Marx", "menentang", "dikritik olehnya"],
    ["Ekonomi klasik dan neoklasik", "pengaruh"],
    ["Frédéric Bastiat", "pengaruh"]
  ],
  "Frederick Winslow Taylor": [
    ["Tradisi teknik mesin Amerika", "pengaruh"],
    ["Henry Ford", "pengaruh"],
    ["Ilmu teknik industri modern", "pengaruh"],
    ["Manajemen operasi kontemporer", "pengaruh"]
  ],
  "John Ruskin": [
    ["J. M. W. Turner", "pengaruh"],
    ["Arsitektur Gothic Italia", "pengaruh"],
    ["Thomas Carlyle", "pengaruh"],
    ["Mahatma Gandhi", "pengaruh"],
    ["Gerakan Arts and Crafts", "pengaruh"],
    ["Sosialisme demokratik Inggris", "pengaruh"]
  ],
  "John Bates Clark": [
    ["Ekonomi kelembagaan Jerman", "pengaruh"],
    ["Revolusi marjinalis", "pengaruh"],
    ["Kritik sosialis terhadap kapitalisme", "pengaruh"],
    ["Ekonomi neoklasik Amerika", "pengaruh"],
    ["Teori distribusi pendapatan modern", "pengaruh"]
  ],
  "Frédéric Bastiat": [
    ["Adam Smith", "pengaruh"],
    ["Richard Cobden", "pengaruh"],
    ["Ekonomi Austria", "pengaruh"],
    ["Gerakan pasar bebas modern", "pengaruh"],
    ["Henry Hazlitt", "pengaruh"]
  ],
  "Booker T. Washington": [
    ["Samuel Chapman Armstrong", "guru", "mentornya di Hampton Institute"],
    ["Frederick Douglass", "pengaruh"],
    ["Etos kerja Protestan", "pengaruh"],
    ["Tuskegee Institute", "pengaruh"],
    ["George Washington Carver", "pengaruh"],
    ["Gerakan pendidikan vokasional Afrika-Amerika", "pengaruh"]
  ],
  "Jane Addams": [
    ["Toynbee Hall", "pengaruh"],
    ["Ellen Gates Starr", "kolaborator", "pendiri bersama Hull House"],
    ["John Dewey", "pengaruh", "pragmatisme Amerika"],
    ["Gerakan pekerjaan sosial modern", "pengaruh"],
    ["Gerakan hak pilih perempuan Amerika", "pengaruh"],
    ["Kebijakan kesejahteraan Progresif", "pengaruh"]
  ],
  "Jacob Riis": [
    ["Teknologi fotografi flash", "pengaruh"],
    ["Gerakan reformasi Progresif", "pengaruh"],
    ["Theodore Roosevelt", "pengaruh"],
    ["Jurnalisme foto dokumenter", "pengaruh"],
    ["Reformasi perumahan perkotaan Amerika", "pengaruh"]
  ],
  "Charlotte Perkins Gilman": [
    ["Gerakan hak pilih perempuan", "pengaruh"],
    ["Herbert Spencer", "menentang", "via kritik"],
    ["Feminisme ekonomi", "pengaruh"],
    ["Studi sastra feminis modern", "pengaruh"],
    ["Kritik terhadap kesehatan mental perempuan", "pengaruh"]
  ],
  "Gustave Le Bon": [
    ["Hippolyte Taine", "pengaruh"],
    ["Komune Paris", "pengaruh"],
    ["Antropologi kolonial Prancis", "pengaruh"],
    ["Sigmund Freud", "pengaruh", "saling memengaruhi"],
    ["Teori propaganda abad ke-20", "pengaruh"],
    ["Psikologi sosial modern", "pengaruh"]
  ],
  "Sigmund Freud": [
    ["Jean-Martin Charcot", "guru", "mentornya di Paris"],
    ["Josef Breuer", "kolaborator", "rekan riset histeria"],
    ["Charles Darwin", "pengaruh"],
    ["Carl Gustav Jung", "murid", "protégé, lalu berpisah"],
    ["Psikoanalisis modern", "pengaruh"],
    ["Gustave Le Bon", "pengaruh", "saling memengaruhi"],
    ["Sastra dan seni abad ke-20", "pengaruh"]
  ],
  "Olive Schreiner": [
    ["Herbert Spencer", "pengaruh"],
    ["Gerakan hak pilih perempuan Inggris", "pengaruh"],
    ["Sastra pascakolonial Afrika Selatan", "pengaruh"]
  ],
  "Samuel Smiles": [
    ["Gerakan Chartist", "pengaruh"],
    ["Benjamin Franklin", "pengaruh"],
    ["Etos kerja Protestan Skotlandia", "pengaruh"],
    ["Genre buku motivasi diri modern", "pengaruh"],
    ["Etika kerja Victoria", "pengaruh"],
    ["Dale Carnegie", "pengaruh"]
  ],
  "Leo Tolstoy": [
    ["Ajaran Yesus", "pengaruh", "pembacaan literal"],
    ["Perang Krimea", "pengaruh"],
    ["Arthur Schopenhauer", "pengaruh"],
    ["Mahatma Gandhi", "pengaruh"],
    ["Martin Luther King Jr.", "pengaruh"],
    ["Gerakan pasifisme Kristen", "pengaruh"]
  ],
  "William Graham Sumner": [
    ["Herbert Spencer", "pengaruh"],
    ["Charles Darwin", "pengaruh"],
    ["Adam Smith", "pengaruh"],
    ["Sosiologi Amerika awal", "pengaruh"],
    ["Libertarianisme Amerika", "pengaruh"],
    ["Kritik terhadap negara kesejahteraan", "pengaruh"]
  ],
  "Henry Adams": [
    ["Tradisi keluarga Adams", "pengaruh"],
    ["Charles Darwin", "pengaruh"],
    ["Perang Saudara Amerika", "pengaruh", "via ayahnya"],
    ["Historiografi Amerika modern", "pengaruh"],
    ["Sastra otobiografi intelektual Amerika", "pengaruh"]
  ]
};

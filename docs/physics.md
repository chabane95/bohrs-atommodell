# Physik des Bohrschen Wasserstoffmodells

Dieses Programm berechnet die Folgen des historischen Bohr-Modells. Die Kreisbahnen sind ausdrücklich Modellannahmen. Es berechnet weder Schrödinger-Orbitale noch experimentell rekonstruierte Elektronenwege oder Bohmsche Trajektorien.

## 1. Modellannahmen und Lernpfad

Die Herleitung beginnt mit zwei klassischen Punktteilchen, Coulombkraft und Schwerpunkttrennung. Ohne zusätzliche Annahmen sind beliebige positive Bahndrehimpulse und entsprechend kontinuierliche Kreisbahnradien möglich. Danach werden Bohrs Postulate eingeführt:

1. Erlaubte Kreisbahnen besitzen den relativen Bahndrehimpuls `L = n hbar` mit positiver ganzer Zahl `n`.
2. Auf diesen erlaubten Bahnen findet trotz beschleunigter Bewegung keine Strahlungsabgabe statt.
3. Beim Übergang zwischen Energieniveaus ist die Photonenenergie gleich der Energiedifferenz.

Diese Postulate folgen nicht aus Newtons Gleichung oder der klassischen Elektrodynamik. Gerade die Strahlungsfreiheit ist eine zusätzliche Annahme. Die folgende Rechnung ist innerhalb dieser Modellannahmen geschlossen. Die Grenzen und der Vergleich zur modernen Quantentheorie sind Teil der Erklärung, nicht nachträgliche numerische Korrekturen. Siehe [David Tong, Cambridge, Abschnitt 4.4.1](https://www.damtp.cam.ac.uk/user/tong/qm/qmhtml/S4.html).

## 2. Schwerpunkt und Relativkoordinate

Für Wasserstoff mit Elektronenmasse `m_e`, Protonenmasse `m_p`, Gesamtmasse `M` und reduzierter Masse `mu` gilt:

$$
M=m_e+m_p,\qquad \mu=\frac{m_em_p}{M},\qquad
\mathbf r=\mathbf r_e-\mathbf r_p,\qquad
\mathbf R=\frac{m_e\mathbf r_e+m_p\mathbf r_p}{M}.
$$

Mit $\kappa=e^2/(4\pi\varepsilon_0)$ zerfällt der klassische Hamiltonian in

$$
H=\frac{\mathbf P^2}{2M}+\frac{\mathbf p^2}{2\mu}-\frac{\kappa}{r}.
$$

Im Programm ruht der Schwerpunkt im Ursprung. Die gespeicherte Radiusgröße ist der Abstand zwischen Elektron und Proton. Die einzelnen Schwerpunktbahnen erfüllen

$$
\mathbf r_e=\frac{m_p}{M}\mathbf r,\qquad
\mathbf r_p=-\frac{m_e}{M}\mathbf r.
$$

Bei `finite_mass=False` ist das Proton fest im Ursprung und `mu = m_e`. Dies ist die übliche Näherung eines unendlich schweren Kerns; die Protonenmasse wird dafür nicht numerisch auf unendlich gesetzt.

## 3. Klassische Kreisbahn und Quantisierung

Für eine Kreisbahn gilt

$$
\frac{\mu v_{\rm rel}^2}{r}=\frac{\kappa}{r^2},\qquad
L=\mu r v_{\rm rel}.
$$

Eliminieren der Geschwindigkeit ergibt zunächst für jeden positiven Drehimpuls

$$
r(L)=\frac{L^2}{\mu\kappa}.
$$

Erst mit dem Postulat $L=n\hbar$ folgen

$$
a_\mu=\frac{\hbar^2}{\mu\kappa},\qquad
r_n=a_\mu n^2,\qquad
v_{{\rm rel},n}=\frac{\kappa}{n\hbar},\qquad
\omega_n=\frac{\mu\kappa^2}{n^3\hbar^3},\qquad
\tau_n=\frac{2\pi}{\omega_n}.
$$

Der konventionelle Bohr-Radius $a_0=\hbar^2/(m_e\kappa)$ verwendet die Elektronenmasse. Die Simulation benutzt standardmäßig $a_\mu=(m_e/\mu)a_0$. Damit ist `radius_m` geringfügig größer als $a_0n^2$. Die Elektronenbahn um den Schwerpunkt hat in diesem korrigierten Bohr-Modell genau den Radius $a_0n^2$; zusätzlich bewegt sich das Proton auf einer kleinen Gegenbahn. `speed_m_s` ist die Relativgeschwindigkeit, nicht die Geschwindigkeit des Elektrons um den Schwerpunkt.

## 4. Energien und effektives Potential

$$
K_n=\frac12\mu v_{{\rm rel},n}^2,
\qquad U_n=-\frac{\kappa}{r_n},
\qquad E_n=-\frac{\mu\kappa^2}{2n^2\hbar^2}.
$$

Es gilt $K_n=-E_n$ und $U_n=2E_n$. Diese Größen sind während einer erlaubten Kreisbewegung konstant. Im Schwerpunkt ist $K_n$ zugleich die Summe der kinetischen Energien beider Teilchen. `energy_ev` entsteht durch Division des Energiewerts in Joule durch die Elementarladung in Coulomb, numerisch der Umrechnungsfaktor Joule pro Elektronenvolt.

Bei festgehaltenem Drehimpuls lautet das effektive Radialpotential

$$
U_{\rm eff}(r;L)=\frac{L^2}{2\mu r^2}-\frac{\kappa}{r}.
$$

Sein Minimum liegt für $L>0$ bei $r=L^2/(\mu\kappa)$. Der erste Term ist der Winkelanteil der kinetischen Energie, keine zusätzliche Wechselwirkung. Das Minimum macht den Kreisbahnradius anschaulich; es erklärt nicht die ganzzahlige Quantisierung. Änderungen von `L` oder `n` in einer Vergleichsanimation sind kein physikalischer Übergangsprozess.

## 5. Exakte Zeitentwicklung innerhalb des Modells

Für eine xy-Bahn und Anfangsphase $\varphi_0$ wird direkt ausgewertet:

$$
\mathbf r(t)=r_n\big(\cos(\omega_nt+\varphi_0),
\sin(\omega_nt+\varphi_0),0\big).
$$

Die Geschwindigkeiten folgen durch analytisches Differenzieren; beide Teilchenpositionen folgen aus den Massenanteilen. Es ist keine numerische Integration nötig. `state_at_time` erlaubt positive und negative physikalische Zeiten in Sekunden. Die Reduktion modulo Umlaufzeit vermeidet das Überlaufen des Produkts `omega*t`; sehr große absolute Gleitkommazeiten verlieren dennoch ihre zeitliche Auflösung. Für Filmframes ist eine kleine, aus Bildindex und Zeitmaßstab berechnete physikalische Zeit vorzuziehen.

Raumrotationen, vergrößerte Teilchenkugeln, Kamerabewegung, Schatten und Filmzeit sind Darstellungsentscheidungen. Ein räumlicher oder zeitlicher Vergleich verschiedener `n` muss einen gemeinsamen Maßstab benutzen oder abweichende Maßstäbe ausdrücklich kennzeichnen. Ein Modellquantensprung darf nicht durch eine behauptete berechnete Spiralbahn ersetzt werden.

## 6. Übergänge und Spektrum

Für eine vorgegebene Emission mit $n_i>n_f$ gilt

$$
E_\gamma=E_{n_i}-E_{n_f}=h\nu,
\qquad \lambda=\frac{hc}{E_\gamma}.
$$

`transition` liefert eine positive Photonenenergie, Frequenz und **Vakuumwellenlänge**. Zum Beispiel liegt die grobe Bohr-Vorhersage für $3\to2$ mit reduzierter Masse bei etwa 656,47 nm im Vakuum. Der häufig genannte Wert um 656,3 nm bezieht sich auf Luft; zusätzlich sind Präzisionswerte von Feinstruktur und weiteren Korrekturen abhängig.

Die Gleichung legt weder Übergangsdauer noch Wahrscheinlichkeit, Intensität, Polarisation oder Auswahlregeln fest. Die Simulation setzt den ausgewählten Übergang voraus. Das Ergebnis ist keine vollständige Atom-Licht-Simulation. Der Rückstoß durch das ausgesandte Photon wird in dieser Bohr-Näherung nicht berücksichtigt. Die Massenkorrektur und die Einordnung gegenüber modernen Wasserstoffdaten beschreibt [A. E. Kramida, NIST, Abschnitt 2](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=842564).

## 7. Vergleich mit dem Orbitalmodell

Bohrs Modell verwendet $L=n\hbar$. Die Schrödinger-Theorie besitzt dagegen $L^2=\ell(\ell+1)\hbar^2$ mit $\ell=0,\ldots,n-1$. Der 1s-Zustand hat daher Bahndrehimpuls null. Seine Wahrscheinlichkeitsdichte ist keine Bohr-Kreisbahn: Für die radiale Verteilung des Grundzustands liegt das Maximum bei $a_\mu$, der mittlere Abstand bei $3a_\mu/2$. Ein späterer Vergleich soll genau diese Unterschiede zeigen, nicht eine Kreisbahn bloß weichzeichnen.

Das Bohr-Spektrum stimmt mit den nichtrelativistischen Coulomb-Energien überein. Die Modellbahnen und die Drehimpulszuordnung werden dadurch nicht zu modernen Elektronenbahnen. Spin, relativistische Korrekturen, Fein- und Hyperfeinstruktur, Lamb-Verschiebung und endliche Protonenausdehnung sind nicht enthalten.

## 8. Konstanten und Prüfungen

Verwendet werden zentrale [CODATA-2022-Werte](https://physics.nist.gov/cuu/pdf/RevModPhys.97.025002.pdf). Die SI-Werte von `h`, `c` und `e` sind exakt definiert; die Messunsicherheiten der anderen Konstanten werden nicht fortgepflanzt. `A0` wird aus den im Code angegebenen Konstanten berechnet. Das ist nicht zwingend bitgleich mit einer separat gerundeten Konstantentabelle.

Die Tests prüfen unabhängige CODATA-Größen, Coulombkraft und Zentripetalbeschleunigung, analytische Skalengesetze, Schwerpunkt und Gesamtimpuls, die kinetische Zweiteilchenidentität, numerische Ableitungen der exakten Bahn, Energie- und Frequenzbeziehungen, Vakuumwellenlängen und die Krümmung des effektiven Potentials. Der Physikkern benötigt nur die Python-Standardbibliothek; seine Produktionsfunktionen enthalten keine Schleifen oder Comprehensions.

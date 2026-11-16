# Series infinitas

Cálculo · Series numéricas y series de Taylor

Fuente: @prof.luisparedes (Instagram), diapositivas 02, 05, 06, 07 y 08 de 15.

---

## Series numéricas

### Geométrica

*Diapositiva 02 de 15*

Razón: $$r = \frac{1}{2}$$

$$\frac{1}{2} + \frac{1}{2^2} + \frac{1}{2^3} + \frac{1}{2^4} + \frac{1}{2^5} + \frac{1}{2^6} + \cdots = 1$$

Razón: $$r = \frac{1}{3}$$

$$\frac{1}{3} + \frac{1}{3^2} + \frac{1}{3^3} + \frac{1}{3^4} + \frac{1}{3^5} + \frac{1}{3^6} + \cdots = \frac{1}{2}$$

**Desarrollo de la serie**

$$\sum_{n=1}^{\infty} r^n = r + r^2 + r^3 + r^4 + r^5 + \cdots = \frac{r}{1 - r}$$

Converge si y solo si: $$|r| < 1$$

### Series p

*Diapositiva 05 de 15*

$$p = 2$$

$$1 + \frac{1}{2^2} + \frac{1}{3^2} + \frac{1}{4^2} + \frac{1}{5^2} + \frac{1}{6^2} + \cdots = \frac{\pi^2}{6}$$

$$p = 4$$

$$1 + \frac{1}{2^4} + \frac{1}{3^4} + \frac{1}{4^4} + \frac{1}{5^4} + \frac{1}{6^4} + \cdots = \frac{\pi^4}{90}$$

**Desarrollo de la serie**

$$\sum_{n=1}^{\infty} \frac{1}{n^p} = 1 + \frac{1}{2^p} + \frac{1}{3^p} + \frac{1}{4^p} + \frac{1}{5^p} + \frac{1}{6^p} + \cdots$$

Converge si y solo si: $$p > 1$$

---

## Series de Taylor

### Exponencial

*Diapositiva 06 de 15*

Ejemplo: $$x = 1$$

$$1 + 1 + \frac{1}{2!} + \frac{1}{3!} + \frac{1}{4!} + \frac{1}{5!} + \cdots = e$$

Ejemplo: $$x = -1$$

$$1 - 1 + \frac{1}{2!} - \frac{1}{3!} + \frac{1}{4!} - \frac{1}{5!} + \cdots = \frac{1}{e}$$

**Desarrollo de la serie**

$$e^x = \sum_{n=0}^{\infty} \frac{x^n}{n!} = 1 + x + \frac{x^2}{2!} + \frac{x^3}{3!} + \frac{x^4}{4!} + \cdots$$

Válida para todo número real: $$x \in \mathbb{R}$$

### Seno

*Diapositiva 07 de 15*

Ejemplo: $$x = \pi$$

$$\pi - \frac{\pi^3}{3!} + \frac{\pi^5}{5!} - \frac{\pi^7}{7!} + \frac{\pi^9}{9!} - \frac{\pi^{11}}{11!} + \cdots = 0$$

**Desarrollo de la serie**

$$\operatorname{sen} x = \sum_{n=0}^{\infty} \frac{(-1)^n x^{2n+1}}{(2n+1)!}$$

$$\operatorname{sen} x = x - \frac{x^3}{3!} + \frac{x^5}{5!} - \frac{x^7}{7!} + \frac{x^9}{9!} - \frac{x^{11}}{11!} + \cdots$$

Válida para todo número real: $$x \in \mathbb{R}$$

### Coseno

*Diapositiva 08 de 15*

Ejemplo: $$x = \pi$$

$$1 - \frac{\pi^2}{2!} + \frac{\pi^4}{4!} - \frac{\pi^6}{6!} + \frac{\pi^8}{8!} - \frac{\pi^{10}}{10!} + \cdots = -1$$

**Desarrollo de la serie**

$$\cos x = \sum_{n=0}^{\infty} \frac{(-1)^n x^{2n}}{(2n)!}$$

$$\cos x = 1 - \frac{x^2}{2!} + \frac{x^4}{4!} - \frac{x^6}{6!} + \frac{x^8}{8!} - \frac{x^{10}}{10!} + \cdots$$

Válida para todo número real: $$x \in \mathbb{R}$$

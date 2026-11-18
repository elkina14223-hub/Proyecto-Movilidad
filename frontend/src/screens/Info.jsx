import { api } from '../api.js'
import Entorno from '../components/Entorno.jsx'
import useDatos, { Estado } from '../useDatos.jsx'

/** RNF-OTR: fuente y periodo de los datos, explicación del IPV, aviso de privacidad y términos. */
export default function Info() {
  const f = useDatos(() => api.fuentes(), [])
  return (
    <>
      <section className="tarjeta">
        <p className="sobre">Transparencia</p>
        <h1>Sobre los datos</h1>
        <Estado {...f}>
          {f.datos && (
            <>
              {f.datos.es_demostracion && (
                <p className="aviso aviso-demo" role="note">
                  Estás viendo datos de demostración. Se reemplazarán por las mediciones reales de la Avenida Pradilla.
                </p>
              )}
              <h2>Fuente y periodo</h2>
              <ul className="simple">
                {f.datos.fuentes.map((x, i) => <li key={i}><strong>{x.fuente}</strong> · {x.periodo}</li>)}
              </ul>
              <h2>¿Qué es el IPV?</h2>
              <p>{f.datos.ipv_explicacion}</p>
            </>
          )}
        </Estado>
      </section>

      <Entorno />

      <section className="tarjeta" id="privacidad">
        <h2>Aviso de privacidad</h2>
        <p>
          Cumplimos la Ley 1581 de 2012. No necesitas crear una cuenta. No guardamos tu IP ni tu ubicación exacta.
          Si en el futuro usamos tu ubicación para mostrarte tu tramo, te pediremos tu consentimiento antes.
          Los reportes se guardan sin datos personales y vencen a los 60 minutos.
        </p>
        <h2 id="terminos">Términos de uso</h2>
        <p>
          La información es orientativa y se basa en datos históricos; no reemplaza las señales de tránsito ni las indicaciones de las autoridades.
          No uses la aplicación mientras conduces.
        </p>
      </section>

      <section className="tarjeta">
        <h2>Qué nos diferencia</h2>
        <ul className="simple">
          <li>Una sola vía: la Avenida Pradilla, con más detalle que una app general.</li>
          <li>Horas pico, alternativas y transporte en un solo lugar.</li>
          <li>Te decimos a qué hora salir, no solo cómo está el tráfico.</li>
          <li>Información de la comunidad, con validación para evitar falsos reportes.</li>
        </ul>
      </section>
    </>
  )
}

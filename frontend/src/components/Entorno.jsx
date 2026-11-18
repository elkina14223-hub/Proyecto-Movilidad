import { api } from '../api.js'
import useDatos, { Estado } from '../useDatos.jsx'

const ESTADOS = {
  operando: { texto: 'Operando', clase: 'ok', icono: '●' },
  vigente: { texto: 'Vigente', clase: 'ok', icono: '●' },
  local: { texto: 'Solo local', clase: 'alerta', icono: '▲' },
  por_vencer: { texto: 'Por vencer', clase: 'alerta', icono: '▲' },
  no_confiable: { texto: 'No confiable (autofirmado)', clase: 'alerta', icono: '▲' },
  degradado: { texto: 'Degradado', clase: 'error', icono: '■' },
  vencido: { texto: 'Vencido', clase: 'error', icono: '■' },
  sin_configurar: { texto: 'Sin configurar', clase: 'alerta', icono: '▲' },
  no_disponible: { texto: 'No disponible', clase: 'error', icono: '■' },
}

function Sello({ estado }) {
  const e = ESTADOS[estado] ?? ESTADOS.no_disponible
  return <span className={`estado estado-${e.clase}`}><span aria-hidden="true">{e.icono}</span> {e.texto}</span>
}

const fecha = (iso) => new Date(iso).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Bogota' })

function Fila({ k, v }) {
  return <div className="fila"><dt>{k}</dt><dd>{v}</dd></div>
}

/** Muestra en la web el estado real de servidor, hosting, dominio y certificado (lo lee del propio servidor). */
export default function Entorno() {
  const e = useDatos(() => api.entorno(), [])
  return (
    <section className="tarjeta" id="entorno">
      <p className="sobre">Infraestructura</p>
      <h1>Entorno de publicación</h1>
      <Estado {...e}>
        {e.datos && (() => {
          const { servidor, hosting, dominio, certificado: c, tls } = e.datos
          return (
            <div className="entorno">
              <article className="caja">
                <h2>Servidor <Sello estado={servidor.estado} /></h2>
                <dl>
                  <Fila k="Servidor web" v={servidor.servidor_web} />
                  <Fila k="Base de datos" v={servidor.base_de_datos} />
                  <Fila k="En línea desde hace" v={`${Math.floor(servidor.en_linea_desde_segundos / 3600)} h ${Math.floor((servidor.en_linea_desde_segundos % 3600) / 60)} min`} />
                </dl>
              </article>

              <article className="caja">
                <h2>Hosting <Sello estado={hosting.configurado ? hosting.estado : 'sin_configurar'} /></h2>
                <dl>
                  <Fila k="Proveedor" v={hosting.proveedor} />
                  <Fila k="Tipo" v={hosting.tipo} />
                  <Fila k="Región" v={hosting.region} />
                </dl>
              </article>

              <article className="caja">
                <h2>Dominio <Sello estado={dominio.estado} /></h2>
                <dl>
                  <Fila k="Nombre" v={<strong>{dominio.nombre}</strong>} />
                  <Fila k="Dominio público" v={dominio.es_dominio_publico ? 'Sí' : 'No (acceso local o por IP)'} />
                  <Fila k="Cubierto por el certificado" v={dominio.certificado_cubre_dominio ? 'Sí' : 'No'} />
                </dl>
              </article>

              <article className="caja">
                <h2>Certificado SSL/TLS <Sello estado={c.disponible ? c.estado : 'no_disponible'} /></h2>
                {c.disponible ? (
                  <dl>
                    {c.gestionado_por && <Fila k="Administrado por" v={`${c.gestionado_por} (emisión y renovación automáticas)`} />}
                    <Fila k="Tipo de validación" v={c.tipo.nombre} />
                    <Fila k="Duración típica" v={c.tipo.duracion_tipica} />
                    <Fila k="Emitido por" v={c.emisor ?? '—'} />
                    <Fila k="Sujeto" v={c.sujeto ?? '—'} />
                    <Fila k="Dominios" v={c.dominios.join(', ') || '—'} />
                    <Fila k="Válido desde" v={fecha(c.valido_desde)} />
                    <Fila k="Válido hasta" v={`${fecha(c.valido_hasta)} (${c.dias_restantes} días)`} />
                    <Fila k="Huella SHA-256" v={<code className="huella">{c.huella_sha256.match(/.{1,2}/g).join(':').toUpperCase()}</code>} />
                    {c.origen && <Fila k="Origen del dato" v={c.origen} />}
                  </dl>
                ) : <p className="nota">{c.motivo}</p>}
              </article>

              {e.datos.mensajeria && (() => {
                const { sincronica: s, asincronica: a } = e.datos.mensajeria
                return (
                  <article className="caja">
                    <h2>Mensajería <Sello estado="operando" /></h2>
                    <dl>
                      <Fila k="Sincrónica · Web" v={`${s.websocket.protocolo} · ${s.websocket.conexiones} conectado(s)`} />
                      <Fila k="Sincrónica · Móvil" v={s.telegram.configurado ? 'Telegram activo' : 'Telegram sin configurar'} />
                      <Fila k="Asincrónica · Correo" v={a.correo.configurado ? `${a.correo.envio} · ${a.correo.destinatarios} destinatario(s)` : 'Correo sin configurar'} />
                      <Fila k="Lectura del buzón" v={a.correo.lectura} />
                    </dl>
                  </article>
                )
              })()}

              <article className="caja">
                <h2>Conexión segura <Sello estado={tls.https_activo ? 'operando' : 'degradado'} /></h2>
                <dl>
                  <Fila k="HTTPS" v={tls.https_activo ? 'Activo' : 'No activo'} />
                  <Fila k="Protocolo" v={tls.protocolo} />
                  <Fila k="Cifrado" v={tls.cifrado} />
                  <Fila k="HSTS" v={tls.hsts} />
                  <Fila k="HTTP → HTTPS" v={`Redirección ${tls.redireccion_http}`} />
                </dl>
              </article>
            </div>
          )
        })()}
      </Estado>
      <p className="nota">Estos datos los lee el propio servidor en este momento; no son una imagen fija.</p>
    </section>
  )
}

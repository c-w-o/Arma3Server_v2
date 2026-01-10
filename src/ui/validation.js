export function makeValidator(schema) {
  const AjvCtor = window.ajv7?.default || window.ajv7 || window.Ajv;

  if (!AjvCtor) {
    // graceful: accept everything but report validation unavailable
    return () => ({ ok: true, errors: [], warning: "AJV not loaded" });
  }

  const ajv = new AjvCtor({ allErrors: true, strict: false, messages: true });
  const validate = ajv.compile(schema);

  return (data) => {
    const ok = validate(data);
    return { ok: !!ok, errors: ok ? [] : (validate.errors || []) };
  };
}
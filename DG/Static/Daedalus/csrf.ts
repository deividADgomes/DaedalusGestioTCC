// Envia automaticamente o token CSRF do Django em toda requisição fetch que altera dados.
(() => {
    const originalFetch = window.fetch.bind(window);

    const lerCookie = (nome: string): string => {
        const par = document.cookie.split('; ').find(c => c.startsWith(nome + '='));
        return par ? decodeURIComponent(par.substring(nome.length + 1)) : '';
    };

    window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
        const metodo = (init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();

        if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(metodo)) {
            const cabecalhos = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
            if (!cabecalhos.has('X-CSRFToken')) {
                cabecalhos.set('X-CSRFToken', lerCookie('csrftoken'));
            }
            init = { ...init, headers: cabecalhos, credentials: init?.credentials ?? 'same-origin' };
        }
        return originalFetch(input, init);
    };
})();

#!/bin/bash
# lanzar_generadores.sh
# Arranca los 10 generadores en segundo plano

echo "Arrancando 10 generadores..."

for i in $(seq -f "%02g" 1 10); do
    python3 generador.py "GEN-$i" --error-prob 0.1 --intervalo 3 &
    echo "  ✓ GEN-$i arrancado (PID $!)"
    sleep 0.2
done

echo ""
echo "Todos los generadores en marcha. Pulsa Ctrl+C para parar."
wait

interface IStringDictionary<V> {
    [index: string]: V;
}

interface INumberDictionary<V> {
    [index: number]: V;
}

type KType = number | string;

export type Dict<K extends KType, V> = IStringDictionary<V> | INumberDictionary<V>;

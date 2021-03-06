interface IStringDictionary<V> {
    [index: string]: V;
}

interface INumberDictionary<V> {
    [index: number]: V;
}

type KType = number | string;

export type Dict<K extends KType, V> = IStringDictionary<V> | INumberDictionary<V>;

export interface JsonArray extends Array<Json> {}
export interface JsonDict extends IStringDictionary<Json> {}
export type Json = null | boolean | number | string | JsonArray | JsonDict;

export type ExternalDependency = any;

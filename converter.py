import sys
import re
import argparse
import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    NAME = "NAME"
    NUMBER = "NUMBER"
    HEX = "HEX"
    STRING = "STRING"
    BOOL_TRUE = "BOOL_TRUE"
    BOOL_FALSE = "BOOL_FALSE"
    LIST_START = "(list"
    LPAREN = "("
    RPAREN = ")"
    STRUCT_START = "struct{"
    STRUCT_END = "}"
    ASSIGN = "="
    COMMA = ","
    DEFINE = ":="
    SEMICOLON = ";"
    LBRACK = "["
    RBRACK = "]"
    CHR_START = "chr("
    PLUS = "+"
    MINUS = "-"
    MUL = "*"
    DIV = "/"
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int


class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1

    def next_token(self) -> Token:
        while self.pos < len(self.text):
            char = self.text[self.pos]

            if char == '#':
                self._skip_line_comment()
                continue
            if char.isspace():
                self._skip_whitespace()
                continue

            if self.pos + 1 < len(self.text) and self.text[self.pos:self.pos + 2] == '{-':
                self._skip_multiline_comment()
                continue

            if self.text[self.pos] == '[':
                expr = self._parse_expression()
                if expr:
                    return expr

            keyword = self._match_keyword()
            if keyword:
                return keyword

            num = self._parse_number()
            if num:
                return num

            string = self._parse_string()
            if string:
                return string

            self.pos += 1
            self.col += 1

        return Token(TokenType.EOF, "", self.line, self.col)

    def _skip_line_comment(self):
        while self.pos < len(self.text) and self.text[self.pos] != '\n':
            self.pos += 1
            self.col += 1
        if self.pos < len(self.text):
            self.line += 1
            self.col = 1

    def _skip_whitespace(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            if self.text[self.pos] == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1

    def _skip_multiline_comment(self):
        self.pos += 2
        self.col += 2
        while self.pos + 1 < len(self.text):
            if self.text[self.pos:self.pos + 2] == '-}':
                self.pos += 2
                self.col += 2
                return
            if self.text[self.pos] == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1

    def _parse_expression(self) -> Optional[Token]:
        start_pos = self.pos
        start_line, start_col = self.line, self.col

        end = self.pos
        bracket_count = 0
        while end < len(self.text):
            if self.text[end] == '[':
                bracket_count += 1
            elif self.text[end] == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    break
            end += 1

        if end == len(self.text) or bracket_count != 0:
            return None

        content = self.text[start_pos + 1:end].strip().split()
        if len(content) >= 2 and content[0] in ['+', '-', '*', '/']:
            value = self.text[start_pos:end + 1]
            token = Token(TokenType.LBRACK, value, start_line, start_col)
            self.pos = end + 1
            self.col = start_col + len(value)
            return token
        return None

    def _parse_number(self) -> Optional[Token]:
        match = re.match(r'0[xX][0-9a-fA-F]+|\d+', self.text[self.pos:])
        if match:
            value = match.group()
            token_type = TokenType.HEX if value.lower().startswith('0x') else TokenType.NUMBER
            token = Token(token_type, value, self.line, self.col)
            self.pos += len(value)
            self.col += len(value)
            return token
        return None

    def _parse_string(self) -> Optional[Token]:
        quote = self.text[self.pos]
        if quote not in ["'", '"']:
            return None

        start_line, start_col = self.line, self.col
        start = self.pos
        self.pos += 1
        self.col += 1

        while self.pos < len(self.text):
            if (self.text[self.pos] == quote and
                    (self.pos == 0 or self.text[self.pos - 1] != '\\')):
                value = self.text[start:self.pos + 1]
                self.pos += 1
                self.col += 1
                return Token(TokenType.STRING, value, start_line, start_col)

            if self.text[self.pos] == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1
        return None

    def _match_keyword(self) -> Optional[Token]:
        patterns = {
            'struct{': TokenType.STRUCT_START,
            '(list': TokenType.LIST_START,
            'chr(': TokenType.CHR_START,
            ':=': TokenType.DEFINE,
            ';': TokenType.SEMICOLON,
            '=': TokenType.ASSIGN,
            ',': TokenType.COMMA,
            '}': TokenType.STRUCT_END,
            ')': TokenType.RPAREN,
            'true': TokenType.BOOL_TRUE,
            'false': TokenType.BOOL_FALSE,
        }

        for pattern, ttype in patterns.items():
            if self.text.startswith(pattern, self.pos):
                token = Token(ttype, pattern, self.line, self.col)
                self.pos += len(pattern)
                self.col += len(pattern)
                return token

        match = re.match(r'[_a-zA-Z][_a-zA-Z0-9]*', self.text[self.pos:])
        if match:
            value = match.group()
            token = Token(TokenType.NAME, value, self.line, self.col)
            self.pos += len(value)
            self.col += len(value)
            return token

        return None


class Parser:
    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.current_token = lexer.next_token()
        self.constants: Dict[str, Any] = {}

    def eat(self, token_type: TokenType):
        if self.current_token.type == token_type:
            self.current_token = self.lexer.next_token()
        else:
            raise SyntaxError(f"{self.current_token.line}:{self.current_token.col}: "
                              f"Ожидался {token_type.value}, получен {self.current_token.type.value}")

    def parse(self) -> Dict[str, Any]:
        result = {}
        while self.current_token.type != TokenType.EOF:
            if self.current_token.type == TokenType.SEMICOLON:
                self.eat(TokenType.SEMICOLON)
                continue

            if self.current_token.type == TokenType.NAME:
                name = self.current_token.value
                self.eat(TokenType.NAME)

                if self.current_token.type == TokenType.DEFINE:
                    self.eat(TokenType.DEFINE)
                    value = self._parse_value()
                    self.constants[name] = value
                    if self.current_token.type == TokenType.SEMICOLON:
                        self.eat(TokenType.SEMICOLON)
                    result[name] = value
                elif self.current_token.type == TokenType.ASSIGN:
                    self.eat(TokenType.ASSIGN)
                    value = self._parse_value()
                    if self.current_token.type == TokenType.SEMICOLON:
                        self.eat(TokenType.SEMICOLON)
                    result[name] = value
                elif self.current_token.type == TokenType.STRUCT_START:
                    value = self._parse_struct()
                    result[name] = value
                else:
                    result[name] = name
            else:
                result["_value"] = self._parse_value()
        return result

    def _parse_value(self) -> Any:
        token = self.current_token

        if token.type in (TokenType.NUMBER, TokenType.HEX):
            value = int(token.value, 16) if token.type == TokenType.HEX else int(token.value)
            self.eat(token.type)
            return value

        if token.type == TokenType.STRING:
            value = token.value[1:-1].replace('\\"', '"').replace("\\'", "'")
            self.eat(token.type)
            return value

        if token.type == TokenType.BOOL_TRUE:
            self.eat(TokenType.BOOL_TRUE)
            return True
        if token.type == TokenType.BOOL_FALSE:
            self.eat(TokenType.BOOL_FALSE)
            return False

        if token.type == TokenType.NAME:
            name = token.value
            if name in self.constants:
                self.eat(TokenType.NAME)
                return self.constants[name]
            self.eat(TokenType.NAME)
            return name

        if token.type == TokenType.LIST_START:
            return self._parse_list()
        if token.type == TokenType.STRUCT_START:
            return self._parse_struct()
        if token.type == TokenType.CHR_START:
            return self._parse_chr()
        if token.type == TokenType.LBRACK:
            return self._parse_expression()

        raise SyntaxError(f"{token.line}:{token.col}: Неожиданное значение: {token.type.value}")

    def _parse_list(self) -> List[Any]:
        self.eat(TokenType.LIST_START)
        result = []
        while self.current_token.type != TokenType.RPAREN and self.current_token.type != TokenType.EOF:
            result.append(self._parse_value())
            if self.current_token.type == TokenType.COMMA:
                self.eat(TokenType.COMMA)
        self.eat(TokenType.RPAREN)
        return result

    def _parse_struct(self) -> Dict[str, Any]:
        result = {}
        self.eat(TokenType.STRUCT_START)

        while self.current_token.type != TokenType.EOF and self.current_token.type != TokenType.STRUCT_END:
            if self.current_token.type != TokenType.NAME:
                self.current_token = self.lexer.next_token()
                continue

            name = self.current_token.value
            self.eat(TokenType.NAME)

            if self.current_token.type != TokenType.ASSIGN:
                raise SyntaxError(f"{self.current_token.line}:{self.current_token.col}: "
                                  f"Ожидался '=', получен {self.current_token.type.value}")

            self.eat(TokenType.ASSIGN)
            value = self._parse_value()
            result[name] = value

            if self.current_token.type == TokenType.COMMA:
                self.eat(TokenType.COMMA)

        self.eat(TokenType.STRUCT_END)
        return result

    def _parse_chr(self) -> str:
        self.eat(TokenType.CHR_START)
        arg = self._parse_value()
        self.eat(TokenType.RPAREN)
        return chr(arg) if isinstance(arg, int) else '?'

    def _parse_expression(self) -> Any:
        expr_str = self.current_token.value
        self.eat(TokenType.LBRACK)

        content = expr_str[1:-1].strip().split()
        if len(content) < 2:
            raise SyntaxError(f"Некорректное выражение: {expr_str}")

        op = content[0]
        if op not in ['+', '-', '*', '/']:
            raise SyntaxError(f"Неизвестная операция: {op}")

        arg1_str = content[1].strip()
        if arg1_str in self.constants:
            arg1 = self.constants[arg1_str]
        else:
            arg1 = int(arg1_str, 16) if arg1_str.lower().startswith('0x') else int(arg1_str)

        if len(content) == 2:
            return arg1

        arg2_str = content[2].strip()
        if arg2_str in self.constants:
            arg2 = self.constants[arg2_str]
        else:
            arg2 = int(arg2_str, 16) if arg2_str.lower().startswith('0x') else int(arg2_str)

        if not isinstance(arg1, int) or not isinstance(arg2, int):
            raise SyntaxError(f"Аргументы должны быть числами: {expr_str}")

        ops = {
            '+': arg1 + arg2,
            '-': arg1 - arg2,
            '*': arg1 * arg2,
            '/': arg1 // arg2 if arg2 != 0 else 0
        }
        return ops[op]


def main():
    parser = argparse.ArgumentParser(description="ВАРИАНТ №31: config -> JSON")
    parser.add_argument('input', nargs='?', default=None, help='Входной файл config')
    parser.add_argument('-o', '--output', required=False, default='output.json',
                        help='Выходной JSON файл (по умолчанию: output.json)')

    args = parser.parse_args()
    output_file = args.output

    if args.input and os.path.exists(args.input):
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
        print(f"Загружен: {args.input}")
    else:
        text = sys.stdin.read()
        if not text.strip():
            print("Входные данные пусты")
            sys.exit(1)

    print("Парсинг...")
    try:
        lexer = Lexer(text)
        parser_obj = Parser(lexer)
        result = parser_obj.parse()

        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Сохранено: {output_file}")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

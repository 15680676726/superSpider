import type { ReactNode } from "react";
import { Form } from "antd";
import { createStyles } from "antd-style";
import type { FormListFieldData, FormListOperation } from "antd";

type FormItemNormalize = (
  value: unknown,
  prevValue: unknown,
  prevValues: unknown,
) => unknown;

type FormListRenderer = (
  fields: FormListFieldData[],
  operations: FormListOperation,
  meta: { errors: ReactNode[]; warnings: ReactNode[] },
) => ReactNode;

type BaseFormItemProps = {
  name: string | string[];
  label: string;
  normalize?: FormItemNormalize;
};

type ListFormItemProps = BaseFormItemProps & {
  isList: true;
  children: FormListRenderer;
};

type FieldFormItemProps = BaseFormItemProps & {
  isList?: false;
  children: ReactNode;
};

type FormItemProps = ListFormItemProps | FieldFormItemProps;

const useStyles = createStyles(({ token }) => ({
  label: {
    marginBottom: 6,
    fontSize: 12,
    color: token.colorTextSecondary,
  },
}));

export default function FormItem(props: FormItemProps) {
  const { styles } = useStyles();

  const node = props.isList ? (
    <Form.List name={props.name}>{props.children}</Form.List>
  ) : (
    <Form.Item name={props.name} normalize={props.normalize}>
      {props.children}
    </Form.Item>
  );

  return (
    <div>
      {props.label && <div className={styles.label}>{props.label}</div>}
      {node}
    </div>
  );
}
